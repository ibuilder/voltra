<?php
/**
 * Plugin Name:       SolSignal Monitor
 * Plugin URI:        https://github.com/REPLACE_OWNER/solsignal
 * Description:        Monitoring + control panel for the SolSignal Freqtrade bots. Talks to the Freqtrade REST API, shows status/PnL/trades, and uses WP-Cron to poll the bots and fire a dry-run tripwire alert. Read-only by default; it never enables live trading.
 * Version:           0.2.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            SolSignal
 * License:           MIT
 * Text Domain:       solsignal-monitor
 *
 * @package SolSignal_Monitor
 *
 * IMPORTANT: this plugin does NOT run the trading bot. The bot is Freqtrade (a
 * 24/7 Python service in Docker). This plugin is only a dashboard/monitor that
 * calls the bot's REST API. It will never set dry_run=false.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // No direct access.
}

define( 'SOLSIGNAL_MON_VERSION', '0.2.0' );
define( 'SOLSIGNAL_MON_DIR', plugin_dir_path( __FILE__ ) );
define( 'SOLSIGNAL_MON_URL', plugin_dir_url( __FILE__ ) );
define( 'SOLSIGNAL_MON_CRON_HOOK', 'solsignal_mon_poll' );

require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-api-client.php';
require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-storage.php';
require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-settings.php';
require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-dashboard.php';
require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-cron.php';
require_once SOLSIGNAL_MON_DIR . 'includes/class-ss-shortcode.php';

/**
 * Boot the plugin.
 */
function solsignal_mon_init() {
	SS_Settings::instance();
	SS_Dashboard::instance();
	SS_Cron::instance();
	SS_Shortcode::instance();
}
add_action( 'plugins_loaded', 'solsignal_mon_init' );

/**
 * Activation: schedule the WP-Cron poll.
 */
function solsignal_mon_activate() {
	SS_Storage::create_table();
	if ( ! wp_next_scheduled( SOLSIGNAL_MON_CRON_HOOK ) ) {
		wp_schedule_event( time() + 60, 'solsignal_mon_15min', SOLSIGNAL_MON_CRON_HOOK );
	}
}
register_activation_hook( __FILE__, 'solsignal_mon_activate' );

/**
 * Deactivation: clear the scheduled event.
 */
function solsignal_mon_deactivate() {
	$ts = wp_next_scheduled( SOLSIGNAL_MON_CRON_HOOK );
	if ( $ts ) {
		wp_unschedule_event( $ts, SOLSIGNAL_MON_CRON_HOOK );
	}
}
register_deactivation_hook( __FILE__, 'solsignal_mon_deactivate' );

/**
 * Custom 15-minute cron schedule.
 *
 * @param array $schedules Existing schedules.
 * @return array
 */
function solsignal_mon_cron_schedules( $schedules ) {
	$schedules['solsignal_mon_15min'] = array(
		'interval' => 15 * MINUTE_IN_SECONDS,
		'display'  => __( 'Every 15 minutes (SolSignal)', 'solsignal-monitor' ),
	);
	return $schedules;
}
add_filter( 'cron_schedules', 'solsignal_mon_cron_schedules' );
