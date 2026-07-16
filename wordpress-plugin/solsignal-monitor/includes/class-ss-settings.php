<?php
/**
 * Settings page (WP Settings API). Stores the list of bots and credentials.
 *
 * SECURITY: the password can be set in the DB here, but for production define
 * SOLSIGNAL_API_PASSWORD in wp-config.php instead — then it never touches the
 * database. The UI warns when the DB value is used.
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Plugin settings storage and settings-page rendering.
 */
class SS_Settings {

	/**
	 * Option name in wp_options.
	 *
	 * @var string
	 */
	const OPTION = 'solsignal_mon_settings';

	/**
	 * Singleton instance.
	 *
	 * @var SS_Settings|null
	 */
	private static $instance = null;

	/**
	 * Get the singleton instance.
	 *
	 * @return SS_Settings
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Hook settings registration.
	 */
	private function __construct() {
		add_action( 'admin_init', array( $this, 'register' ) );
	}

	/**
	 * Get the stored settings merged with defaults.
	 *
	 * @return array Settings with defaults.
	 */
	public static function get() {
		$defaults = array(
			'bots'            => "solsignal-dry|http://127.0.0.1:8080\nsolsignal-cross|http://127.0.0.1:8081\nsolsignal-webhook|http://127.0.0.1:8082",
			'username'        => 'solsignal',
			'password'        => '',
			'alert_email'     => get_option( 'admin_email' ),
			'enable_controls' => 0,
		);
		return wp_parse_args( get_option( self::OPTION, array() ), $defaults );
	}

	/**
	 * Resolve the effective password (wp-config constant wins).
	 *
	 * @return string
	 */
	public static function password() {
		if ( defined( 'SOLSIGNAL_API_PASSWORD' ) && SOLSIGNAL_API_PASSWORD ) {
			return SOLSIGNAL_API_PASSWORD;
		}
		$s = self::get();
		return isset( $s['password'] ) ? $s['password'] : '';
	}

	/**
	 * Parse the "name|url" lines into an array of bots.
	 *
	 * @return array<int,array{name:string,url:string}>
	 */
	public static function bots() {
		$s    = self::get();
		$bots = array();
		foreach ( preg_split( '/\r\n|\r|\n/', (string) $s['bots'] ) as $line ) {
			$line = trim( $line );
			if ( '' === $line || false === strpos( $line, '|' ) ) {
				continue;
			}
			list( $name, $url ) = array_map( 'trim', explode( '|', $line, 2 ) );
			if ( $name && $url ) {
				$bots[] = array(
					'name' => $name,
					'url'  => esc_url_raw( $url ),
				);
			}
		}
		return $bots;
	}

	/**
	 * Register the setting with the Settings API.
	 */
	public function register() {
		register_setting(
			'solsignal_mon',
			self::OPTION,
			array( 'sanitize_callback' => array( $this, 'sanitize' ) )
		);
	}

	/**
	 * Sanitize submitted settings.
	 *
	 * @param mixed $input Raw submitted values.
	 * @return array Sanitized settings.
	 */
	public function sanitize( $input ) {
		$out = self::get();
		if ( isset( $input['bots'] ) ) {
			$out['bots'] = sanitize_textarea_field( $input['bots'] );
		}
		if ( isset( $input['username'] ) ) {
			$out['username'] = sanitize_text_field( $input['username'] );
		}
		if ( isset( $input['password'] ) ) {
			// Only overwrite if a new value was typed (blank keeps existing).
			if ( '' !== $input['password'] ) {
				$out['password'] = $input['password'];
			}
		}
		if ( isset( $input['alert_email'] ) ) {
			$out['alert_email'] = sanitize_email( $input['alert_email'] );
		}
		$out['enable_controls'] = empty( $input['enable_controls'] ) ? 0 : 1;
		return $out;
	}

	/**
	 * Render the settings form (called from the admin page).
	 */
	public static function render_form() {
		$s           = self::get();
		$using_const = defined( 'SOLSIGNAL_API_PASSWORD' ) && SOLSIGNAL_API_PASSWORD;
		?>
		<form method="post" action="options.php">
			<?php settings_fields( 'solsignal_mon' ); ?>
			<table class="form-table" role="presentation">
				<tr>
					<th scope="row"><label for="ss_bots"><?php esc_html_e( 'Bots (name|url per line)', 'solsignal-monitor' ); ?></label></th>
					<td><textarea id="ss_bots" name="<?php echo esc_attr( self::OPTION ); ?>[bots]" rows="4" class="large-text code"><?php echo esc_textarea( $s['bots'] ); ?></textarea></td>
				</tr>
				<tr>
					<th scope="row"><label for="ss_user"><?php esc_html_e( 'API username', 'solsignal-monitor' ); ?></label></th>
					<td><input id="ss_user" type="text" name="<?php echo esc_attr( self::OPTION ); ?>[username]" value="<?php echo esc_attr( $s['username'] ); ?>" class="regular-text"></td>
				</tr>
				<tr>
					<th scope="row"><label for="ss_pass"><?php esc_html_e( 'API password', 'solsignal-monitor' ); ?></label></th>
					<td>
						<?php if ( $using_const ) : ?>
							<em><?php esc_html_e( 'Using SOLSIGNAL_API_PASSWORD from wp-config.php (recommended).', 'solsignal-monitor' ); ?></em>
						<?php else : ?>
							<input id="ss_pass" type="password" name="<?php echo esc_attr( self::OPTION ); ?>[password]" value="" placeholder="<?php echo $s['password'] ? esc_attr__( '(unchanged)', 'solsignal-monitor' ) : ''; ?>" class="regular-text" autocomplete="new-password">
							<p class="description"><?php esc_html_e( 'Stored in the database. For better security, define SOLSIGNAL_API_PASSWORD in wp-config.php instead.', 'solsignal-monitor' ); ?></p>
						<?php endif; ?>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="ss_email"><?php esc_html_e( 'Alert email', 'solsignal-monitor' ); ?></label></th>
					<td><input id="ss_email" type="email" name="<?php echo esc_attr( self::OPTION ); ?>[alert_email]" value="<?php echo esc_attr( $s['alert_email'] ); ?>" class="regular-text"></td>
				</tr>
				<tr>
					<th scope="row"><?php esc_html_e( 'Advanced controls', 'solsignal-monitor' ); ?></th>
					<td>
						<label><input type="checkbox" name="<?php echo esc_attr( self::OPTION ); ?>[enable_controls]" value="1" <?php checked( $s['enable_controls'], 1 ); ?>>
						<?php esc_html_e( 'Enable start/stop and force-exit buttons (off by default). Never enables live trading.', 'solsignal-monitor' ); ?></label>
					</td>
				</tr>
			</table>
			<?php submit_button(); ?>
		</form>
		<?php
	}
}
