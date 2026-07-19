<?php
/**
 * WP-Cron poller: every 15 min, fetch each bot's summary, cache it for the
 * dashboard, and fire the DRY-RUN TRIPWIRE (email) if any bot reports
 * dry_run=false — an unauthorized live bot is treated as an incident.
 *
 * NOTE: WP-Cron fires on page loads. For reliable scheduling on a low-traffic
 * site, disable it (define('DISABLE_WP_CRON', true) in wp-config.php) and add a
 * real system cron: * /15 * * * * curl -s https://site/wp-cron.php?doing_wp_cron
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * WP-Cron poller and alerting for the SolSignal bots.
 */
class SS_Cron {

	/**
	 * Transient key for the cached snapshot.
	 *
	 * @var string
	 */
	const SNAPSHOT = 'solsignal_mon_snapshot';

	/**
	 * Option key tracking which bots already tripped.
	 *
	 * @var string
	 */
	const TRIP_FLAG = 'solsignal_mon_tripped';

	/**
	 * Singleton instance.
	 *
	 * @var SS_Cron|null
	 */
	private static $instance = null;

	/**
	 * Get the singleton instance.
	 *
	 * @return SS_Cron
	 */
	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	/**
	 * Hook the cron action.
	 */
	private function __construct() {
		add_action( SOLSIGNAL_MON_CRON_HOOK, array( $this, 'poll' ) );
	}

	/**
	 * Poll all bots, store a snapshot, and alert on the tripwire.
	 */
	public function poll() {
		$s        = SS_Settings::get();
		$pass     = SS_Settings::password();
		$snapshot = array(
			'time' => time(),
			'bots' => array(),
		);

		foreach ( SS_Settings::bots() as $bot ) {
			$client             = new SS_Api_Client( $bot['url'], $s['username'], $pass );
			$summary            = $client->summary();
			$summary['name']    = $bot['name'];
			$snapshot['bots'][] = $summary;

			// Persist this reading to the time-series table (data collection).
			SS_Storage::record( $bot['name'], $summary );

			// Tripwire: live-mode bot.
			if ( isset( $summary['dry_run'] ) && false === $summary['dry_run'] ) {
				$this->trip( $bot['name'], $s['alert_email'] );
			}
			// Unreachable alert, debounced by a transient.
			if ( empty( $summary['reachable'] ) ) {
				$this->maybe_alert_unreachable( $bot['name'], $summary['error'], $s['alert_email'] );
			}
		}

		set_transient( self::SNAPSHOT, $snapshot, HOUR_IN_SECONDS );
		SS_Storage::prune(); // bound table growth (default 1 year retention)
	}

	/**
	 * Fire the dry-run tripwire email once per incident.
	 *
	 * @param string $bot   Bot name.
	 * @param string $email Alert recipient.
	 */
	private function trip( $bot, $email ) {
		$already = (array) get_option( self::TRIP_FLAG, array() );
		if ( in_array( $bot, $already, true ) ) {
			return; // Already alerted for this bot.
		}
		$already[] = $bot;
		update_option( self::TRIP_FLAG, $already, false );

		if ( $email ) {
			wp_mail(
				$email,
				'[SolSignal CRITICAL] Bot is LIVE — dry_run=false',
				sprintf(
					"Bot '%s' reports dry_run=false.\n\nGoing live is a human-only change. If you did not authorize this, treat it as a security incident: stop the bot and rotate credentials.\n\n-- SolSignal Monitor",
					$bot
				)
			);
		}
	}

	/**
	 * Alert once per hour for an unreachable bot.
	 *
	 * @param string $bot   Bot name.
	 * @param string $error Error message.
	 * @param string $email Alert recipient.
	 */
	private function maybe_alert_unreachable( $bot, $error, $email ) {
		$key = 'ss_mon_unreach_' . md5( $bot );
		if ( get_transient( $key ) ) {
			return;
		}
		set_transient( $key, 1, HOUR_IN_SECONDS );
		if ( $email ) {
			wp_mail(
				$email,
				'[SolSignal WARN] Bot unreachable: ' . $bot,
				sprintf( "Bot '%s' is unreachable: %s\n\n-- SolSignal Monitor", $bot, $error )
			);
		}
	}

	/**
	 * Get the last cached snapshot.
	 *
	 * @return array|false Snapshot array, or false if none.
	 */
	public static function snapshot() {
		return get_transient( self::SNAPSHOT );
	}
}
