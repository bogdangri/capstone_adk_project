DO $$
/* ****************************************************************************************************
 * Request: 123458
 * Scope  : N/A
 * User   : automation_agent
 * Start  : 2025-11-27T18:21:44.613590
 **************************************************************************************************** */

-- Generated as a PostgreSQL PL/pgSQL DO-block
DECLARE
  v_request_id text := '123458';
  v_started_at timestamptz := now();
  v_rows int;
  v_err_text text;
  v_err_state text;
BEGIN
  RAISE NOTICE 'Request % started at %', v_request_id, v_started_at;

  /* Existing fee tariff found, expiring the old one. */
  -- 1) expire current row(s)
  UPDATE public.fee_tariff
     SET data_out = CURRENT_DATE
   WHERE id='1'
     AND data_out IS NULL;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RAISE NOTICE 'Expired % row(s) in % for keys [id=''1'']', v_rows, 'public.fee_tariff';

  IF v_rows = 0 THEN
    RAISE EXCEPTION 'No active row to expire in % for keys [%]', 'public.fee_tariff', 'id=''1'''
      USING ERRCODE = 'no_data_found';
  END IF;

  -- 2) insert new version
  INSERT INTO public.fee_tariff (date_out, data_in, data_out) VALUES (CURRENT_DATE, CURRENT_DATE, NULL);
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RAISE NOTICE 'Inserted % row(s) into %', v_rows, 'public.fee_tariff';

               /* Inserting new fee tariff as a fixed value with id=4. */
                 INSERT INTO public.fee_tariff (fee_id, currency, tariff_amount, tariff_percent, min_amount, max_amount, created_by, data_in, data_out)
                 VALUES ('136', 'ROL', '20', '0', '1.00', NULL, '1111', CURRENT_DATE, NULL);
                 GET DIAGNOSTICS v_rows = ROW_COUNT;
                 RAISE NOTICE 'Inserted % row(s) into %', v_rows, 'public.fee_tariff';
            
  RAISE NOTICE 'Request % completed successfully', v_request_id;

EXCEPTION
  WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS
      v_err_text  = MESSAGE_TEXT,
      v_err_state = RETURNED_SQLSTATE;
    RAISE NOTICE 'Request % failed: % (SQLSTATE=%)', v_request_id, v_err_text, v_err_state;
    RAISE;
END;

$$ LANGUAGE plpgsql;
