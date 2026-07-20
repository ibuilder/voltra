<?php
/**
 * Admin menu + dashboard page + AJAX endpoints (live refresh and, if enabled,
 * guarded control actions).
 *
 * @package Voltra_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Registers the admin menu, dashboard page, and AJAX handlers.
 */
class VT_Dashboard {

	/**
	 * Capability required for all actions.
	 *
	 * @var string
	 */
	const CAP = 'manage_options';

	/**
	 * Singleton instance.
	 *
	 * @var VT_Dashboard|null
	 */
	private static $instance = null;

	/**
	 * Get the singleton instance.
	 *
	 * @return VT_Dashboard
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Hook the admin menu and AJAX endpoints.
	 */
	private function __construct() {
		add_action( 'admin_menu', array( $this, 'menu' ) );
		add_action( 'wp_ajax_voltra_mon_status', array( $this, 'ajax_status' ) );
		add_action( 'wp_ajax_voltra_mon_action', array( $this, 'ajax_action' ) );
		add_action( 'admin_post_voltra_mon_export', array( $this, 'export_csv' ) );
	}

	/**
	 * Stream the collected time-series as a CSV download.
	 */
	public function export_csv() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( 'forbidden', '', array( 'response' => 403 ) );
		}
		check_admin_referer( 'voltra_mon_export' );
		$rows = VT_Storage::recent( 100000 );
		nocache_headers();
		header( 'Content-Type: text/csv; charset=utf-8' );
		header( 'Content-Disposition: attachment; filename=voltra-data.csv' );
		$out  = fopen( 'php://output', 'w' );
		$cols = array( 'captured_at', 'bot', 'reachable', 'dry_run', 'state', 'strategy', 'balance', 'open_trades', 'closed_trades', 'pnl' );
		fputcsv( $out, $cols );
		foreach ( (array) $rows as $r ) {
			$line = array();
			foreach ( $cols as $c ) {
				$line[] = isset( $r[ $c ] ) ? $r[ $c ] : '';
			}
			fputcsv( $out, $line );
		}
		fclose( $out ); // phpcs:ignore WordPress.WP.AlternativeFunctions.file_system_operations_fclose
		exit;
	}

	/**
	 * Register the top-level admin menu page.
	 */
	public function menu() {
		$hook = add_menu_page(
			__( 'Voltra', 'voltra-monitor' ),
			__( 'Voltra', 'voltra-monitor' ),
			self::CAP,
			'voltra-monitor',
			array( $this, 'render' ),
			'dashicons-chart-line'
		);
		add_action( 'load-' . $hook, array( $this, 'noop' ) );
	}

	/**
	 * Placeholder load hook (kept for future per-screen setup).
	 */
	public function noop() {}

	/**
	 * Live status via AJAX (server calls the bot APIs; creds never hit JS).
	 */
	public function ajax_status() {
		check_ajax_referer( 'voltra_mon' );
		if ( ! current_user_can( self::CAP ) ) {
			wp_send_json_error( 'forbidden', 403 );
		}
		$s    = VT_Settings::get();
		$pass = VT_Settings::password();
		$out  = array();
		foreach ( VT_Settings::bots() as $bot ) {
			$client      = new VT_Api_Client( $bot['url'], $s['username'], $pass );
			$sum         = $client->summary();
			$sum['name'] = $bot['name'];
			$out[]       = $sum;
		}
		wp_send_json_success( $out );
	}

	/**
	 * Guarded control actions (only when enabled in settings). Never touches
	 * dry_run — only start/stop the trade loop or force-exit an open trade.
	 */
	public function ajax_action() {
		check_ajax_referer( 'voltra_mon' );
		if ( ! current_user_can( self::CAP ) ) {
			wp_send_json_error( 'forbidden', 403 );
		}
		$s = VT_Settings::get();
		if ( empty( $s['enable_controls'] ) ) {
			wp_send_json_error( 'controls disabled', 403 );
		}
		$bot_url = isset( $_POST['bot'] ) ? esc_url_raw( wp_unslash( $_POST['bot'] ) ) : '';
		$action  = isset( $_POST['do'] ) ? sanitize_key( $_POST['do'] ) : '';
		$allowed = array( 'start', 'stop', 'reload_config' );
		if ( ! in_array( $action, $allowed, true ) || ! $bot_url ) {
			wp_send_json_error( 'bad request', 400 );
		}
		// Freqtrade RPC actions are POST endpoints.
		$client = new VT_Api_Client( $bot_url, $s['username'], VT_Settings::password() );
		$res    = $client->post( '/' . $action );
		if ( is_wp_error( $res ) ) {
			wp_send_json_error( $res->get_error_message() );
		}
		wp_send_json_success( $res );
	}

	/**
	 * Render the dashboard admin page.
	 */
	public function render() {
		if ( ! current_user_can( self::CAP ) ) {
			return;
		}
		$controls = ! empty( VT_Settings::get()['enable_controls'] );
		?>
		<div class="wrap">
			<h1>Voltra Monitor</h1>
			<p class="description">
				<?php esc_html_e( 'Read-only monitor for your Freqtrade bots. This plugin never enables live trading.', 'voltra-monitor' ); ?>
			</p>

			<h2 class="nav-tab-wrapper">
				<a href="#dash" class="nav-tab nav-tab-active"><?php esc_html_e( 'Dashboard', 'voltra-monitor' ); ?></a>
				<a href="#history" class="nav-tab"><?php esc_html_e( 'Collected data', 'voltra-monitor' ); ?></a>
				<a href="#settings" class="nav-tab"><?php esc_html_e( 'Settings', 'voltra-monitor' ); ?></a>
			</h2>

			<div id="ss-dash">
				<p><button class="button" id="ss-refresh"><?php esc_html_e( 'Refresh', 'voltra-monitor' ); ?></button> <span id="ss-updated"></span></p>
				<table class="widefat striped" id="ss-table">
					<thead><tr>
						<th><?php esc_html_e( 'Bot', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'Mode', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'State', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'Strategy', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'Balance', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'Open', 'voltra-monitor' ); ?></th>
						<th><?php esc_html_e( 'Closed PnL', 'voltra-monitor' ); ?></th>
						<?php
						if ( $controls ) :
							?>
							<th><?php esc_html_e( 'Controls', 'voltra-monitor' ); ?></th><?php endif; ?>
					</tr></thead>
					<tbody><tr><td colspan="8"><?php esc_html_e( 'Loading…', 'voltra-monitor' ); ?></td></tr></tbody>
				</table>
			</div>

			<div id="ss-history" style="display:none;">
				<?php $this->render_history(); ?>
			</div>

			<div id="ss-settings" style="display:none;">
				<?php VT_Settings::render_form(); ?>
			</div>
		</div>
		<script>
			window.SS_MON = {
				ajax: <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>,
				nonce: <?php echo wp_json_encode( wp_create_nonce( 'voltra_mon' ) ); ?>,
				controls: <?php echo $controls ? 'true' : 'false'; ?>
			};
		</script>
		<?php
		$this->inline_assets();
	}

	/**
	 * Render the collected-data (history) view with a CSV export button.
	 */
	private function render_history() {
		$total  = VT_Storage::count();
		$rows   = VT_Storage::recent( 200 );
		$export = wp_nonce_url( admin_url( 'admin-post.php?action=voltra_mon_export' ), 'voltra_mon_export' );
		?>
		<p>
			<?php
			printf(
				/* translators: %s: number of collected rows. */
				esc_html__( '%s data points collected. Newest 200 shown.', 'voltra-monitor' ),
				esc_html( number_format_i18n( $total ) )
			);
			?>
			&nbsp;<a class="button button-primary" href="<?php echo esc_url( $export ); ?>"><?php esc_html_e( 'Download CSV', 'voltra-monitor' ); ?></a>
		</p>
		<table class="widefat striped">
			<thead><tr>
				<th><?php esc_html_e( 'Time (UTC)', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'Bot', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'dry_run', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'State', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'Balance', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'Open', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'Closed', 'voltra-monitor' ); ?></th>
				<th><?php esc_html_e( 'PnL', 'voltra-monitor' ); ?></th>
			</tr></thead>
			<tbody>
			<?php if ( empty( $rows ) ) : ?>
				<tr><td colspan="8"><?php esc_html_e( 'No data yet — the first cron poll will populate this.', 'voltra-monitor' ); ?></td></tr>
			<?php else : ?>
				<?php foreach ( $rows as $r ) : ?>
					<tr>
						<td><?php echo esc_html( $r['captured_at'] ); ?></td>
						<td><?php echo esc_html( $r['bot'] ); ?></td>
						<td><?php echo null === $r['dry_run'] ? '—' : ( $r['dry_run'] ? 'yes' : 'LIVE' ); ?></td>
						<td><?php echo esc_html( $r['state'] ); ?></td>
						<td><?php echo esc_html( $r['balance'] ); ?></td>
						<td><?php echo esc_html( $r['open_trades'] ); ?></td>
						<td><?php echo esc_html( $r['closed_trades'] ); ?></td>
						<td><?php echo esc_html( $r['pnl'] ); ?></td>
					</tr>
				<?php endforeach; ?>
			<?php endif; ?>
			</tbody>
		</table>
		<?php
	}

	/**
	 * Minimal inline JS/CSS (keeps the plugin single-purpose, no build step).
	 */
	private function inline_assets() {
		?>
		<style>
			.ss-live{color:#0073aa;font-weight:600}.ss-dry{color:#00844a;font-weight:700}
			#ss-table td.ok{color:#00844a}#ss-table td.bad{color:#b32d2e}
		</style>
		<script>
		(function(){
			var C = window.SS_MON;
			function tab(sel){document.querySelectorAll('.nav-tab').forEach(function(a){a.classList.remove('nav-tab-active')});
				document.getElementById('ss-dash').style.display = sel==='#dash'?'':'none';
				document.getElementById('ss-history').style.display = sel==='#history'?'':'none';
				document.getElementById('ss-settings').style.display = sel==='#settings'?'':'none';}
			document.querySelectorAll('.nav-tab').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();
				a.classList.add('nav-tab-active');tab(a.getAttribute('href'));});});
			function money(v){return v==null?'—':'$'+Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});}
			function row(b){
				if(!b.reachable) return '<tr><td>'+b.name+'</td><td colspan="6" class="bad">unreachable: '+(b.error||'')+'</td></tr>';
				var mode = b.dry_run===false ? '<span class="ss-live">LIVE ⚠</span>' : '<span class="ss-dry">DRY-RUN</span>';
				var pnlCls = b.pnl>=0?'ok':'bad';
				var ctl = C.controls ? '<td><button class="button ss-act" data-bot="'+b.url+'" data-do="stop">Stop</button> <button class="button ss-act" data-bot="'+b.url+'" data-do="start">Start</button></td>' : '';
				return '<tr><td>'+b.name+'</td><td>'+mode+'</td><td>'+(b.state||'')+'</td><td>'+(b.strategy||'')+'</td><td>'+money(b.balance)+'</td><td>'+b.open+'</td><td class="'+pnlCls+'">'+money(b.pnl)+'</td>'+ctl+'</tr>';
			}
			function refresh(){
				var body = new URLSearchParams({action:'voltra_mon_status',_ajax_nonce:C.nonce});
				fetch(C.ajax,{method:'POST',body:body,credentials:'same-origin'}).then(function(r){return r.json();}).then(function(j){
					var tb = document.querySelector('#ss-table tbody');
					if(!j.success){tb.innerHTML='<tr><td colspan="8" class="bad">error</td></tr>';return;}
					tb.innerHTML = j.data.map(row).join('');
					document.getElementById('ss-updated').textContent = 'updated '+new Date().toLocaleTimeString();
					if(C.controls){document.querySelectorAll('.ss-act').forEach(function(btn){btn.addEventListener('click',function(){
						var body=new URLSearchParams({action:'voltra_mon_action',_ajax_nonce:C.nonce,bot:btn.dataset.bot,do:btn.dataset.do});
						fetch(C.ajax,{method:'POST',body:body,credentials:'same-origin'}).then(function(r){return r.json();}).then(refresh);});});}
				});
			}
			document.getElementById('ss-refresh').addEventListener('click',refresh);
			refresh(); setInterval(refresh, 30000);
		})();
		</script>
		<?php
	}
}
