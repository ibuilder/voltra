<?php
/**
 * Optional read-only status shortcode: [solsignal_status]
 *
 * Renders the cached WP-Cron snapshot only (no live credentialed calls on the
 * front end). Safe to place on a private/admin-only page. Shows mode + PnL.
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Read-only [solsignal_status] shortcode rendering the cached cron snapshot.
 */
class SS_Shortcode {

	/**
	 * Singleton instance.
	 *
	 * @var SS_Shortcode|null
	 */
	private static $instance = null;

	/**
	 * Get the singleton instance.
	 *
	 * @return SS_Shortcode
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Register the shortcode.
	 */
	private function __construct() {
		add_shortcode( 'solsignal_status', array( $this, 'render' ) );
	}

	/**
	 * Render the status table from the cached snapshot.
	 *
	 * @param array $atts Shortcode attributes (unused).
	 * @return string HTML.
	 */
	public function render( $atts ) {
		unset( $atts );
		$snap = SS_Cron::snapshot();
		if ( ! $snap || empty( $snap['bots'] ) ) {
			return '<p>' . esc_html__( 'SolSignal: no data yet (waiting for the first cron poll).', 'solsignal-monitor' ) . '</p>';
		}
		$rows = '';
		foreach ( $snap['bots'] as $b ) {
			if ( empty( $b['reachable'] ) ) {
				$rows .= '<tr><td>' . esc_html( $b['name'] ) . '</td><td colspan="3">' . esc_html__( 'unreachable', 'solsignal-monitor' ) . '</td></tr>';
				continue;
			}
			$mode  = ( isset( $b['dry_run'] ) && false === $b['dry_run'] )
				? '<strong style="color:#0073aa">LIVE</strong>'
				: '<strong style="color:#00844a">DRY-RUN</strong>';
			$rows .= sprintf(
				'<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>',
				esc_html( $b['name'] ),
				$mode,
				esc_html( isset( $b['strategy'] ) ? $b['strategy'] : '' ),
				esc_html( number_format( (float) ( isset( $b['pnl'] ) ? $b['pnl'] : 0 ), 2 ) )
			);
		}
		$updated = esc_html( gmdate( 'Y-m-d H:i', (int) $snap['time'] ) . ' UTC' );
		return '<table class="solsignal-status"><thead><tr><th>Bot</th><th>Mode</th><th>Strategy</th><th>Closed PnL</th></tr></thead><tbody>'
			. $rows . '</tbody></table><p><small>updated ' . $updated . '</small></p>';
	}
}
