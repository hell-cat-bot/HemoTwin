# forecast-v2 fold-0 nadir GBDT — feature contract

Ordered feature columns for the fold-0 3-seed GBDT dumps in this
directory (LightGBM `Booster.save_model` text format; trained by
`scripts/task03_refit_nadir.py`, segment forecast-v2). Feature
values are produced exactly as in the frozen Task 01 pipeline:
`src.features.causal_anchor_features` (v4_causal, pre-anchor only)
+ `src.features.session_history_features` (strictly earlier
sessions) + `src.actual_uf.gbdt_uf_features` at the target horizon.

- `nadir_seed{42,43,44}.txt`: predict `observed_nadir` (the
  60-min cuff-sampled nadir); UF block at horizon 60.
- `60_seed{42,43,44}.txt`: predict `observed_60`; UF block
  at horizon 60.
- `30_seed{42,43,44}.txt`: predict `observed_30`; UF block
  at horizon 30.
- Ensemble prediction = mean of the 3 seed boosters.
- LightGBM handles NaN feature values natively; no imputation is
  applied (same as training). All features are numeric.

## Feature order (nadir / 60-minute models)

1. sbp_now
2. dbp_now
3. map_now
4. sbp_mean_15
5. sbp_min_15
6. sbp_slope_15
7. sbp_mean_30
8. sbp_min_30
9. sbp_slope_30
10. sbp_mean_60
11. sbp_min_60
12. sbp_slope_60
13. sbp_mean_120
14. sbp_min_120
15. sbp_slope_120
16. sbp_drop_from_max
17. n_bp_so_far
18. uf_Lh
19. blood_flow
20. conductivity
21. dia_temp
22. cum_uf_L
23. age
24. sex_M
25. dm
26. vintage_years
27. dry_weight
28. pre_weight
29. uf_goal_L
30. elapsed_min
31. uf_ml_kg_h
32. frac_uf_done
33. uf_slope_15
34. uf_slope_30
35. uf_var_30
36. uf_over13
37. cond_dev
38. temp_dev
39. sbp_std_30
40. sbp_std_60
41. pulse_pressure
42. map_slope_30
43. gap_since_last
44. n_bp_60
45. month
46. k_pat
47. beta_pat
48. twin_D_now
49. twin_refill_Lh
50. twin_refill_ratio
51. twin_pred_nadir
52. hist_idh_rate10
53. hist_mean_nadir3
54. hist_mean_nadir10
55. hist_prev_nadir
56. hist_mean_first_sbp3
57. hist_early_crash10
58. hist_last_idh
59. hist_n_sessions
60. horizon_min
61. uf_future_at_h
62. uf_cum_h
63. uf_mean_h
64. uf_min_h
65. uf_max_h
66. uf_seg_1_15
67. uf_seg_16_30
68. uf_seg_31_45
69. uf_seg_46_60
70. uf_zero_share_h
71. uf_reduction_ref_h
72. uf_slope_60

## Feature order (30-minute model)

1. sbp_now
2. dbp_now
3. map_now
4. sbp_mean_15
5. sbp_min_15
6. sbp_slope_15
7. sbp_mean_30
8. sbp_min_30
9. sbp_slope_30
10. sbp_mean_60
11. sbp_min_60
12. sbp_slope_60
13. sbp_mean_120
14. sbp_min_120
15. sbp_slope_120
16. sbp_drop_from_max
17. n_bp_so_far
18. uf_Lh
19. blood_flow
20. conductivity
21. dia_temp
22. cum_uf_L
23. age
24. sex_M
25. dm
26. vintage_years
27. dry_weight
28. pre_weight
29. uf_goal_L
30. elapsed_min
31. uf_ml_kg_h
32. frac_uf_done
33. uf_slope_15
34. uf_slope_30
35. uf_var_30
36. uf_over13
37. cond_dev
38. temp_dev
39. sbp_std_30
40. sbp_std_60
41. pulse_pressure
42. map_slope_30
43. gap_since_last
44. n_bp_60
45. month
46. k_pat
47. beta_pat
48. twin_D_now
49. twin_refill_Lh
50. twin_refill_ratio
51. twin_pred_nadir
52. hist_idh_rate10
53. hist_mean_nadir3
54. hist_mean_nadir10
55. hist_prev_nadir
56. hist_mean_first_sbp3
57. hist_early_crash10
58. hist_last_idh
59. hist_n_sessions
60. horizon_min
61. uf_future_at_h
62. uf_cum_h
63. uf_mean_h
64. uf_min_h
65. uf_max_h
66. uf_seg_1_15
67. uf_seg_16_30
68. uf_seg_31_45
69. uf_seg_46_60
70. uf_zero_share_h
71. uf_reduction_ref_h
72. uf_slope_60

## Excluded from the frozen candidate set

Identifiers/meta (`session_id`, `pid`, `t_anchor`, `regime`,
`n_prior_sessions`) and every outcome-window or post-anchor column
(`cuffs`, `cuff_sbp`, `offsets`, `off30`, `off60`, `t30`, `t60`,
`obs30`, `obs60`, `observed_nadir`, `coverage_complete`,
`max_gap_min`, raw `future` UF vector, raw `reference_uf`,
`oracle_*`, `dbp_anchor`) are never features. The UF-oracle block
(`horizon_min`..`uf_slope_60`) is retained because it is part of
the frozen Task 01 GBDT feature list (actual machine-logged UF
programme, not the BP outcome) and the substrate's regime column
is derived from the same oracle. See
`artifacts/review_20261108/task03_refit_report.json` for the full
justification.
