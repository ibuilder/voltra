<?php
/**
 * Uninstall cleanup: remove options + scheduled events + transients.
 *
 * @package Voltra_Monitor
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'voltra_mon_settings' );
delete_option( 'voltra_mon_tripped' );
delete_transient( 'voltra_mon_snapshot' );

// Drop the collected-data table.
require_once plugin_dir_path( __FILE__ ) . 'includes/class-vt-storage.php';
if ( class_exists( 'VT_Storage' ) ) {
	VT_Storage::drop_table();
}

$ts = wp_next_scheduled( 'voltra_mon_poll' );
if ( $ts ) {
	wp_unschedule_event( $ts, 'voltra_mon_poll' );
}
