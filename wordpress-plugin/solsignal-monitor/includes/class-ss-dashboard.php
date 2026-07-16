<?php
/**
 * Admin menu + dashboard page + AJAX endpoints (live refresh and, if enabled,
 * guarded control actions).
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Registers the admin menu, dashboard page, and AJAX handlers.
 */
class SS_Dashboard {

	/**
	 * Capability required for all actions.
	 *
	 * @var string
	 */
	const CAP = 'manage_options';

	/**
	 * Singleton instance.
	 *
	 * @var SS_Dashboard|null
	 */
	private static $instance = null;

	/**
	 * Get the singleton instance.
	 *
	 * @return SS_Dashboard
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
		add_action( 'wp_ajax_ss_mon_status', array( $this, 'ajax_status' ) );
		add_action( 'wp_ajax_ss_mon_action', array( $this, 'ajax_action' ) );
	}

	/**
	 * Register the top-level admin menu page.
	 */
	public function menu() {
		$hook = add_menu_page(
			__( 'SolSignal', 'solsignal-monitor' ),
			__( 'SolSignal', 'solsignal-monitor' ),
			self::CAP,
			'solsignal-monitor',
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
		check_ajax_referer( 'ss_mon' );
		if ( ! current_user_can( self::CAP ) ) {
			wp_send_json_error( 'forbidden', 403 );
		}
		$s    = SS_Settings::get();
		$pass = SS_Settings::password();
		$out  = array();
		foreach ( SS_Settings::bots() as $bot ) {
			$client      = new SS_Api_Client( $bot['url'], $s['username'], $pass );
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
		check_ajax_referer( 'ss_mon' );
		if ( ! current_user_can( self::CAP ) ) {
			wp_send_json_error( 'forbidden', 403 );
		}
		$s = SS_Settings::get();
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
		$client = new SS_Api_Client( $bot_url, $s['username'], SS_Settings::password() );
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
		$controls = ! empty( SS_Settings::get()['enable_controls'] );
		?>
		<div class="wrap">
			<h1>SolSignal Monitor</h1>
			<p class="description">
				<?php esc_html_e( 'Read-only monitor for your Freqtrade bots. This plugin never enables live trading.', 'solsignal-monitor' ); ?>
			</p>

			<h2 class="nav-tab-wrapper">
				<a href="#dash" class="nav-tab nav-tab-active"><?php esc_html_e( 'Dashboard', 'solsignal-monitor' ); ?></a>
				<a href="#settings" class="nav-tab"><?php esc_html_e( 'Settings', 'solsignal-monitor' ); ?></a>
			</h2>

			<div id="ss-dash">
				<p><button class="button" id="ss-refresh"><?php esc_html_e( 'Refresh', 'solsignal-monitor' ); ?></button> <span id="ss-updated"></span></p>
				<table class="widefat striped" id="ss-table">
					<thead><tr>
						<th><?php esc_html_e( 'Bot', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'Mode', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'State', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'Strategy', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'Balance', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'Open', 'solsignal-monitor' ); ?></th>
						<th><?php esc_html_e( 'Closed PnL', 'solsignal-monitor' ); ?></th>
						<?php
						if ( $controls ) :
							?>
							<th><?php esc_html_e( 'Controls', 'solsignal-monitor' ); ?></th><?php endif; ?>
					</tr></thead>
					<tbody><tr><td colspan="8"><?php esc_html_e( 'Loading…', 'solsignal-monitor' ); ?></td></tr></tbody>
				</table>
			</div>

			<div id="ss-settings" style="display:none;">
				<?php SS_Settings::render_form(); ?>
			</div>
		</div>
		<script>
			window.SS_MON = {
				ajax: <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>,
				nonce: <?php echo wp_json_encode( wp_create_nonce( 'ss_mon' ) ); ?>,
				controls: <?php echo $controls ? 'true' : 'false'; ?>
			};
		</script>
		<?php
		$this->inline_assets();
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
				var body = new URLSearchParams({action:'ss_mon_status',_ajax_nonce:C.nonce});
				fetch(C.ajax,{method:'POST',body:body,credentials:'same-origin'}).then(function(r){return r.json();}).then(function(j){
					var tb = document.querySelector('#ss-table tbody');
					if(!j.success){tb.innerHTML='<tr><td colspan="8" class="bad">error</td></tr>';return;}
					tb.innerHTML = j.data.map(row).join('');
					document.getElementById('ss-updated').textContent = 'updated '+new Date().toLocaleTimeString();
					if(C.controls){document.querySelectorAll('.ss-act').forEach(function(btn){btn.addEventListener('click',function(){
						var body=new URLSearchParams({action:'ss_mon_action',_ajax_nonce:C.nonce,bot:btn.dataset.bot,do:btn.dataset.do});
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
