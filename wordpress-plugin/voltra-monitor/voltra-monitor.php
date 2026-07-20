<?php
/**
 * Plugin Name:       Voltra Monitor
 * Plugin URI:        https://github.com/ibuilder/voltra
 * Description:        Monitoring + control panel for the Voltra Freqtrade bots. Talks to the Freqtrade REST API, shows status/PnL/trades, and uses WP-Cron to poll the bots and fire a dry-run tripwire alert. Read-only by default; it never enables live trading.
 * Version:           0.2.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Voltra
 * License:           MIT
 * Text Domain:       voltra-monitor
 *
 * @package Voltra_Monitor
 *
 * IMPORTANT: this plugin does NOT run the trading bot. The bot is Freqtrade (a
 * 24/7 Python service in Docker). This plugin is only a dashboard/monitor that
 * calls the bot's REST API. It will never set dry_run=false.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit; // No direct access.
}

define( 'VOLTRA_MON_VERSION', '0.2.0' );
define( 'VOLTRA_MON_DIR', plugin_dir_path( __FILE__ ) );
define( 'VOLTRA_MON_URL', plugin_dir_url( __FILE__ ) );
define( 'VOLTRA_MON_CRON_HOOK', 'voltra_mon_poll' );

require_once VOLTRA_MON_DIR . 'includes/class-vt-api-client.php';
require_once VOLTRA_MON_DIR . 'includes/class-vt-storage.php';
require_once VOLTRA_MON_DIR . 'includes/class-vt-settings.php';
require_once VOLTRA_MON_DIR . 'includes/class-vt-dashboard.php';
require_once VOLTRA_MON_DIR . 'includes/class-vt-cron.php';
require_once VOLTRA_MON_DIR . 'includes/class-vt-shortcode.php';

/**
 * Boot the plugin.
 */
function voltra_mon_init() {
	VT_Settings::instance();
	VT_Dashboard::instance();
	VT_Cron::instance();
	VT_Shortcode::instance();
}
add_action( 'plugins_loaded', 'voltra_mon_init' );

/**
 * Activation: schedule the WP-Cron poll.
 */
function voltra_mon_activate() {
	VT_Storage::create_table();
	if ( ! wp_next_scheduled( VOLTRA_MON_CRON_HOOK ) ) {
		wp_schedule_event( time() + 60, 'voltra_mon_15min', VOLTRA_MON_CRON_HOOK );
	}
}
register_activation_hook( __FILE__, 'voltra_mon_activate' );

/**
 * Deactivation: clear the scheduled event.
 */
function voltra_mon_deactivate() {
	$ts = wp_next_scheduled( VOLTRA_MON_CRON_HOOK );
	if ( $ts ) {
		wp_unschedule_event( $ts, VOLTRA_MON_CRON_HOOK );
	}
}
register_deactivation_hook( __FILE__, 'voltra_mon_deactivate' );

/**
 * Custom 15-minute cron schedule.
 *
 * @param array $schedules Existing schedules.
 * @return array
 */
function voltra_mon_cron_schedules( $schedules ) {
	$schedules['voltra_mon_15min'] = array(
		'interval' => 15 * MINUTE_IN_SECONDS,
		'display'  => __( 'Every 15 minutes (Voltra)', 'voltra-monitor' ),
	);
	return $schedules;
}
add_filter( 'cron_schedules', 'voltra_mon_cron_schedules' );
