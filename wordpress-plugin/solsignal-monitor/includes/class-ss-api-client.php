<?php
/**
 * Freqtrade REST API client (server-side only — credentials never reach the
 * browser). JWT token is cached in a transient.
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Api_Client {

	/** @var string */
	private $base_url;
	/** @var string */
	private $user;
	/** @var string */
	private $pass;
	/** @var string */
	private $cache_key;

	/**
	 * @param string $base_url e.g. http://127.0.0.1:8080
	 * @param string $user
	 * @param string $pass
	 */
	public function __construct( $base_url, $user, $pass ) {
		$this->base_url  = untrailingslashit( $base_url );
		$this->user      = $user;
		$this->pass      = $pass;
		$this->cache_key = 'ss_mon_token_' . md5( $this->base_url . $this->user );
	}

	/**
	 * Get a bearer token, using the cached one if present.
	 *
	 * @param bool $force Force a fresh login.
	 * @return string|WP_Error
	 */
	private function token( $force = false ) {
		if ( ! $force ) {
			$cached = get_transient( $this->cache_key );
			if ( $cached ) {
				return $cached;
			}
		}
		$resp = wp_remote_post(
			$this->base_url . '/api/v1/token/login',
			array(
				'timeout' => 10,
				'headers' => array(
					'Authorization' => 'Basic ' . base64_encode( $this->user . ':' . $this->pass ),
				),
			)
		);
		if ( is_wp_error( $resp ) ) {
			return $resp;
		}
		$code = wp_remote_retrieve_response_code( $resp );
		if ( 200 !== (int) $code ) {
			return new WP_Error( 'ss_login', sprintf( 'login failed (HTTP %d)', $code ) );
		}
		$body  = json_decode( wp_remote_retrieve_body( $resp ), true );
		$token = isset( $body['access_token'] ) ? $body['access_token'] : '';
		if ( ! $token ) {
			return new WP_Error( 'ss_login', 'no access_token in response' );
		}
		// Freqtrade access tokens are short-lived; cache under that.
		set_transient( $this->cache_key, $token, 10 * MINUTE_IN_SECONDS );
		return $token;
	}

	/**
	 * GET a REST path, refreshing the token once on 401.
	 *
	 * @param string $path e.g. /status
	 * @return array|WP_Error Decoded JSON.
	 */
	public function get( $path ) {
		foreach ( array( false, true ) as $force ) {
			$token = $this->token( $force );
			if ( is_wp_error( $token ) ) {
				return $token;
			}
			$resp = wp_remote_get(
				$this->base_url . '/api/v1' . $path,
				array(
					'timeout' => 12,
					'headers' => array( 'Authorization' => 'Bearer ' . $token ),
				)
			);
			if ( is_wp_error( $resp ) ) {
				return $resp;
			}
			$code = (int) wp_remote_retrieve_response_code( $resp );
			if ( 401 === $code && ! $force ) {
				delete_transient( $this->cache_key );
				continue; // retry with a fresh token
			}
			if ( 200 !== $code ) {
				return new WP_Error( 'ss_api', sprintf( '%s -> HTTP %d', $path, $code ) );
			}
			return json_decode( wp_remote_retrieve_body( $resp ), true );
		}
		return new WP_Error( 'ss_api', 'unreachable' );
	}

	/**
	 * Convenience: fetch a compact status summary for one bot.
	 *
	 * @return array {reachable, dry_run, state, strategy, balance, open, closed, pnl, error}
	 */
	public function summary() {
		$cfg = $this->get( '/show_config' );
		if ( is_wp_error( $cfg ) ) {
			return array( 'reachable' => false, 'error' => $cfg->get_error_message() );
		}
		$profit  = $this->get( '/profit' );
		$balance = $this->get( '/balance' );
		$status  = $this->get( '/status' );

		return array(
			'reachable' => true,
			'dry_run'   => isset( $cfg['dry_run'] ) ? (bool) $cfg['dry_run'] : null,
			'state'     => isset( $cfg['state'] ) ? $cfg['state'] : '',
			'strategy'  => isset( $cfg['strategy'] ) ? $cfg['strategy'] : '',
			'bot_name'  => isset( $cfg['bot_name'] ) ? $cfg['bot_name'] : '',
			'balance'   => is_array( $balance ) && isset( $balance['total'] ) ? (float) $balance['total'] : null,
			'open'      => is_array( $status ) ? count( $status ) : 0,
			'closed'    => is_array( $profit ) && isset( $profit['closed_trade_count'] ) ? (int) $profit['closed_trade_count'] : 0,
			'pnl'       => is_array( $profit ) && isset( $profit['profit_closed_coin'] ) ? (float) $profit['profit_closed_coin'] : 0.0,
			'error'     => '',
		);
	}
}
