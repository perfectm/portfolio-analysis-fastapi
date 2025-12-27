-- Cleanup script for orphaned foreign key references in SQLite
-- Run this before migration to remove data referencing deleted portfolios

.echo on

-- Show counts before cleanup
SELECT '=== BEFORE CLEANUP ===' as status;

SELECT 'Total portfolios' as description, COUNT(*) as count FROM portfolios;

SELECT 'portfolio_data records' as table_name, COUNT(*) as count FROM portfolio_data
UNION ALL
SELECT 'portfolio_margin_data', COUNT(*) FROM portfolio_margin_data
UNION ALL
SELECT 'blended_portfolio_mappings', COUNT(*) FROM blended_portfolio_mappings
UNION ALL
SELECT 'analysis_results', COUNT(*) FROM analysis_results
UNION ALL
SELECT 'analysis_plots', COUNT(*) FROM analysis_plots;

-- Find orphaned records
SELECT '=== ORPHANED RECORDS ===' as status;

SELECT 'Orphaned portfolio_data' as table_name, COUNT(*) as orphaned_count
FROM portfolio_data pd
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = pd.portfolio_id)
UNION ALL
SELECT 'Orphaned portfolio_margin_data', COUNT(*)
FROM portfolio_margin_data pmd
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = pmd.portfolio_id)
UNION ALL
SELECT 'Orphaned blended_portfolio_mappings', COUNT(*)
FROM blended_portfolio_mappings bpm
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = bpm.portfolio_id)
UNION ALL
SELECT 'Orphaned analysis_results', COUNT(*)
FROM analysis_results ar
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = ar.portfolio_id);

-- Delete orphaned records
SELECT '=== CLEANING UP ===' as status;

DELETE FROM portfolio_data
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = portfolio_id);

DELETE FROM portfolio_margin_data
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = portfolio_id);

DELETE FROM blended_portfolio_mappings
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = portfolio_id);

DELETE FROM analysis_results
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = portfolio_id);

DELETE FROM analysis_plots
WHERE NOT EXISTS (SELECT 1 FROM analysis_results ar WHERE ar.id = analysis_result_id);

-- Delete blended portfolios that have no valid mappings left
DELETE FROM blended_portfolios
WHERE id NOT IN (SELECT DISTINCT blended_portfolio_id FROM blended_portfolio_mappings);

-- Show counts after cleanup
SELECT '=== AFTER CLEANUP ===' as status;

SELECT 'portfolio_data records' as table_name, COUNT(*) as count FROM portfolio_data
UNION ALL
SELECT 'portfolio_margin_data', COUNT(*) FROM portfolio_margin_data
UNION ALL
SELECT 'blended_portfolio_mappings', COUNT(*) FROM blended_portfolio_mappings
UNION ALL
SELECT 'blended_portfolios', COUNT(*) FROM blended_portfolios
UNION ALL
SELECT 'analysis_results', COUNT(*) FROM analysis_results
UNION ALL
SELECT 'analysis_plots', COUNT(*) FROM analysis_plots;

-- Verify no orphans remain
SELECT '=== VERIFICATION ===' as status;

SELECT 'Remaining orphaned portfolio_data' as check_name, COUNT(*) as should_be_zero
FROM portfolio_data pd
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = pd.portfolio_id)
UNION ALL
SELECT 'Remaining orphaned portfolio_margin_data', COUNT(*)
FROM portfolio_margin_data pmd
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = pmd.portfolio_id)
UNION ALL
SELECT 'Remaining orphaned blended_portfolio_mappings', COUNT(*)
FROM blended_portfolio_mappings bpm
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = bpm.portfolio_id)
UNION ALL
SELECT 'Remaining orphaned analysis_results', COUNT(*)
FROM analysis_results ar
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.id = ar.portfolio_id);

SELECT '=== CLEANUP COMPLETE ===' as status;
