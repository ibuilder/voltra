<?php
/**
 * Persistent time-series storage for bot snapshots.
 *
 * Each WP-Cron poll writes one row per bot into a custom table, so history
 * accumulates for analysis/export. This is the plugin's data-collection layer.
 *
 * Direct $wpdb calls on a custom table are unavoidable and are the documented
 * WordPress pattern; each is annotated. Table names cannot be bound as
 * placeholders, so they are interpolated from $wpdb->prefix (trusted).
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Custom-table storage for collected bot snapshots.
 */
class SS_Storage {

	/**
	 * Unprefixed table name.
	 *
	 * @var string
	 */
	const TABLE = 'solsignal_snapshots';

	/**
	 * Full, prefixed table name.
	 *
	 * @return string
	 */
	public static function table() {
		global $wpdb;
		return $wpdb->prefix . self::TABLE;
	}

	/**
	 * Create or upgrade the table (called on activation).
	 */
	public static function create_table() {
		global $wpdb;
		$table   = self::table();
		$charset = $wpdb->get_charset_collate();
		$sql     = "CREATE TABLE {$table} (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			captured_at DATETIME NOT NULL,
			bot VARCHAR(64) NOT NULL,
			reachable TINYINT(1) NOT NULL DEFAULT 0,
			dry_run TINYINT(1) DEFAULT NULL,
			state VARCHAR(32) DEFAULT '',
			strategy VARCHAR(64) DEFAULT '',
			balance DECIMAL(20,8) DEFAULT NULL,
			open_trades INT DEFAULT 0,
			closed_trades INT DEFAULT 0,
			pnl DECIMAL(20,8) DEFAULT 0,
			PRIMARY KEY  (id),
			KEY captured_at (captured_at),
			KEY bot (bot)
		) {$charset};";
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		// dbDelta creates/updates the plugin's own table on activation.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.SchemaChange
		dbDelta( $sql );
	}

	/**
	 * Record one bot snapshot.
	 *
	 * @param string $bot     Bot name.
	 * @param array  $summary Summary from SS_Api_Client::summary().
	 */
	public static function record( $bot, $summary ) {
		global $wpdb;
		$dry = null;
		if ( array_key_exists( 'dry_run', $summary ) && null !== $summary['dry_run'] ) {
			$dry = $summary['dry_run'] ? 1 : 0;
		}
		// Insert into the custom table; $wpdb->insert escapes all values.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching
		$wpdb->insert(
			self::table(),
			array(
				'captured_at'   => gmdate( 'Y-m-d H:i:s' ),
				'bot'           => (string) $bot,
				'reachable'     => empty( $summary['reachable'] ) ? 0 : 1,
				'dry_run'       => $dry,
				'state'         => isset( $summary['state'] ) ? (string) $summary['state'] : '',
				'strategy'      => isset( $summary['strategy'] ) ? (string) $summary['strategy'] : '',
				'balance'       => isset( $summary['balance'] ) ? $summary['balance'] : null,
				'open_trades'   => isset( $summary['open'] ) ? (int) $summary['open'] : 0,
				'closed_trades' => isset( $summary['closed'] ) ? (int) $summary['closed'] : 0,
				'pnl'           => isset( $summary['pnl'] ) ? $summary['pnl'] : 0,
			),
			array( '%s', '%s', '%d', '%d', '%s', '%s', '%f', '%d', '%d', '%f' )
		);
	}

	/**
	 * Most recent rows (newest first).
	 *
	 * @param int $limit Max rows.
	 * @return array Row arrays.
	 */
	public static function recent( $limit = 200 ) {
		global $wpdb;
		$table = self::table();
		// Read from the custom table; table name interpolated from trusted prefix.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching, WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
		return $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$table} ORDER BY captured_at DESC LIMIT %d", (int) $limit ), ARRAY_A );
	}

	/**
	 * Total row count.
	 *
	 * @return int
	 */
	public static function count() {
		global $wpdb;
		$table = self::table();
		// Count rows in the custom table.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching, WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
		return (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table}" );
	}

	/**
	 * Delete rows older than N days to bound growth.
	 *
	 * @param int $days Retention window.
	 */
	public static function prune( $days = 365 ) {
		global $wpdb;
		$table  = self::table();
		$cutoff = gmdate( 'Y-m-d H:i:s', time() - $days * DAY_IN_SECONDS );
		// Retention maintenance on the custom table.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching, WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
		$wpdb->query( $wpdb->prepare( "DELETE FROM {$table} WHERE captured_at < %s", $cutoff ) );
	}

	/**
	 * Drop the table (uninstall).
	 */
	public static function drop_table() {
		global $wpdb;
		$table = self::table();
		// Drop the custom table on uninstall; name interpolated from trusted prefix.
		// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching, WordPress.DB.DirectDatabaseQuery.SchemaChange, WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
		$wpdb->query( "DROP TABLE IF EXISTS {$table}" );
	}
}
