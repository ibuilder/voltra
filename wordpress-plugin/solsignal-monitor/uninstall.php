<?php
/**
 * Uninstall cleanup: remove options + scheduled events + transients.
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'solsignal_mon_settings' );
delete_option( 'solsignal_mon_tripped' );
delete_transient( 'solsignal_mon_snapshot' );

$ts = wp_next_scheduled( 'solsignal_mon_poll' );
if ( $ts ) {
	wp_unschedule_event( $ts, 'solsignal_mon_poll' );
}
