<?php
/**
 * Freqtrade REST API client.
 *
 * Server-side only — credentials never reach the browser. The JWT token is
 * cached in a transient and refreshed once on a 401.
 *
 * @package SolSignal_Monitor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Thin authenticated client for one Freqtrade bot's REST API.
 */
class SS_Api_Client {

	/**
	 * Bot base URL, e.g. http://127.0.0.1:8080.
	 *
	 * @var string
	 */
	private $base_url;

	/**
	 * REST username.
	 *
	 * @var string
	 */
	private $user;

	/**
	 * REST password.
	 *
	 * @var string
	 */
	private $pass;

	/**
	 * Transient key for the cached token.
	 *
	 * @var string
	 */
	private $cache_key;

	/**
	 * Constructor.
	 *
	 * @param string $base_url Bot base URL.
	 * @param string $user     REST username.
	 * @param string $pass     REST password.
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
	 * @return string|WP_Error Token string, or error.
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
					// HTTP Basic auth header; base64 is required by the scheme, not obfuscation.
					'Authorization' => 'Basic ' . base64_encode( $this->user . ':' . $this->pass ), // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions.obfuscation_base64_encode
				),
			)
		);
		if ( is_wp_error( $resp ) ) {
			return $resp;
		}
		$code = (int) wp_remote_retrieve_response_code( $resp );
		if ( 200 !== $code ) {
			return new WP_Error( 'ss_login', sprintf( 'login failed (HTTP %d)', $code ) );
		}
		$body  = json_decode( wp_remote_retrieve_body( $resp ), true );
		$token = isset( $body['access_token'] ) ? $body['access_token'] : '';
		if ( ! $token ) {
			return new WP_Error( 'ss_login', 'no access_token in response' );
		}
		set_transient( $this->cache_key, $token, 10 * MINUTE_IN_SECONDS );
		return $token;
	}

	/**
	 * Perform an authenticated request, refreshing the token once on a 401.
	 *
	 * @param string $method HTTP method (GET or POST).
	 * @param string $path   REST path, e.g. /status.
	 * @return array|WP_Error Decoded JSON, or error.
	 */
	private function request( $method, $path ) {
		foreach ( array( false, true ) as $force ) {
			$token = $this->token( $force );
			if ( is_wp_error( $token ) ) {
				return $token;
			}
			$args = array(
				'timeout' => 12,
				'headers' => array( 'Authorization' => 'Bearer ' . $token ),
			);
			$url  = $this->base_url . '/api/v1' . $path;
			$resp = ( 'POST' === $method ) ? wp_remote_post( $url, $args ) : wp_remote_get( $url, $args );
			if ( is_wp_error( $resp ) ) {
				return $resp;
			}
			$code = (int) wp_remote_retrieve_response_code( $resp );
			if ( 401 === $code && ! $force ) {
				delete_transient( $this->cache_key );
				continue;
			}
			if ( 200 !== $code ) {
				return new WP_Error( 'ss_api', sprintf( '%s -> HTTP %d', $path, $code ) );
			}
			return json_decode( wp_remote_retrieve_body( $resp ), true );
		}
		return new WP_Error( 'ss_api', 'unreachable' );
	}

	/**
	 * Authenticated GET.
	 *
	 * @param string $path REST path, e.g. /status.
	 * @return array|WP_Error Decoded JSON, or error.
	 */
	public function get( $path ) {
		return $this->request( 'GET', $path );
	}

	/**
	 * Authenticated POST (Freqtrade RPC actions like /start, /stop are POST).
	 *
	 * @param string $path REST path, e.g. /start.
	 * @return array|WP_Error Decoded JSON, or error.
	 */
	public function post( $path ) {
		return $this->request( 'POST', $path );
	}

	/**
	 * Fetch a compact status summary for one bot.
	 *
	 * @return array Summary with reachable, dry_run, state, strategy, balance, open, closed, pnl, error.
	 */
	public function summary() {
		$cfg = $this->get( '/show_config' );
		if ( is_wp_error( $cfg ) ) {
			return array(
				'reachable' => false,
				'error'     => $cfg->get_error_message(),
			);
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
