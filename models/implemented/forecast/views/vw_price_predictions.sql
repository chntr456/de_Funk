-- View: vw_price_predictions
-- Purpose: Unified view combining historical actuals with forecast predictions
-- Used by: forecast_chart exhibit in notebooks

-- Historical actuals (from company model)
WITH actuals AS (
    SELECT
        trade_date as date,
        ticker,
        NULL as model_name,
        close as actual,
        NULL as predicted,
        NULL as upper_bound,
        NULL as lower_bound
    FROM company.fact_prices
),

-- Future predictions (from forecast model)
predictions AS (
    SELECT
        prediction_date as date,
        ticker,
        model_name,
        NULL as actual,
        predicted_close as predicted,
        upper_bound,
        lower_bound
    FROM forecast.fact_forecasts
)

-- Combine both
SELECT * FROM actuals
UNION ALL
SELECT * FROM predictions
ORDER BY date, ticker, model_name
