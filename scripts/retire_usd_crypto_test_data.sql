-- Stop gateway writers and back up the named test database before apply=true.
\set ON_ERROR_STOP on
\if :{?expected_database}
\else
  \echo 'expected_database is required'
  \quit 3
\endif
\if :{?apply}
\else
  \set apply false
\endif
SELECT current_database() = :'expected_database'
       AND current_database() LIKE 'dev-%' AS allowed_database \gset
\if :allowed_database
\else
  \echo 'Refusing cleanup outside the explicitly named test database'
  \quit 3
\endif
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
CREATE TEMP TABLE retained_symbols AS
SELECT * FROM supported_symbols WHERE symbol NOT IN ('BTC/USD', 'ETH/USD', 'BTCUSD', 'ETHUSD');
CREATE TEMP TABLE retained_candle_count AS
SELECT count(*) AS total FROM market_data_candles
WHERE symbol NOT IN ('BTC/USD', 'ETH/USD', 'BTCUSD', 'ETHUSD');
SELECT symbol, provider, provider_symbol, count(*) FROM market_data_candles
WHERE symbol IN ('BTC/USD', 'ETH/USD', 'BTCUSD', 'ETHUSD') GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
DELETE FROM market_data_candles WHERE symbol IN ('BTC/USD', 'ETH/USD', 'BTCUSD', 'ETHUSD');
-- The registry migration replaces these rows after this explicit test cleanup.
DELETE FROM supported_symbols WHERE symbol IN ('BTC/USD', 'ETH/USD', 'BTCUSD', 'ETHUSD');
DO $$
BEGIN
    IF EXISTS (SELECT * FROM retained_symbols EXCEPT SELECT * FROM supported_symbols)
       OR EXISTS (SELECT * FROM supported_symbols EXCEPT SELECT * FROM retained_symbols)
       OR (SELECT count(*) FROM market_data_candles) <> (SELECT total FROM retained_candle_count) THEN
        RAISE EXCEPTION 'Unrelated MDG symbols or candle counts changed';
    END IF;
END $$;
\if :apply
  COMMIT;
\else
  ROLLBACK;
\endif
