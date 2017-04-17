library(RSQLite)
library(ggplot2)
library(dplyr)

GAMMA_RATIO <- 4
N_BOOTSTRAPS = 10000

MODELS_ALL <- list(
   list(dirname = 'model0-null/cost_duration', label = 'Null'),
#list(dirname = 'model0-null/cost_transmission', label = 'Null (T)'),
   list(dirname = 'model1-aam/cost_duration', label = 'AAM'),
   list(dirname = 'model2-ast/cost_duration', label = 'AST'),
list(dirname = 'model5-psi/cost_duration', label = 'PSI'),
list(dirname = 'model9-psi+aam+ast/cost_duration', label = 'AAM+AST+PSI'),
   #list(dirname = 'model3-st', label = 'st'),
   list(dirname = 'model4-ct/cost_duration', label = 'CT-EIC'),
list(dirname = 'model16-ct-eih/cost_duration', label = 'CT-EIH'),
   list(dirname = 'model6-aam+ast+ct+psi/cost_duration', label = 'AAM+AST+CT-EIC+PSI'),
   list(dirname = 'model7-psi+aam+ast+ct+eih/cost_duration', label = 'AAM+AST+CT-EIH+PSI'),
#   list(dirname = 'model8-psi+ct+eih/cost_duration', label = 'CT-EIH+PSI'),
#list(dirname = 'model9-psi+aam+ast/cost_transmission', label = 'AAM+AST+PSI (T)'),
   #list(dirname = 'model10-psi+st', label = 'st+psi'),
#   list(dirname = 'model11-psi+ast/cost_duration', label = 'AST+PSI'),
#   list(dirname = 'model12-psi+aam/cost_duration', label = 'AAM+PSI'),
   list(dirname = 'model13-treat=5-aam+ast+ct-eih+psi/cost_duration', label = 'ST+AAM+AST+CT-EIH+PSI'),
   list(dirname = 'model14-treat=20-aam+ast+ct-eih+psi/cost_duration', label = 'LT+AAM+AST+CT-EIH+PSI')
#   list(dirname = 'model15-aam+ast/cost_duration', label = 'AAM+AST'),
#list(dirname = 'model16-ct-eih/cost_transmission', label = 'CT-EIH (T)')
)

save_all_formats <- function(prefix, p, width, height)
{
    ggsave(sprintf('%s.eps', prefix), p, width=width, height=height)
    ggsave(sprintf('%s.pdf', prefix), p, width=width, height=height)
    ggsave(sprintf('%s.png', prefix), p, width=width, height=height, dpi = 150)
}

load_query <- function(filename, query)
{
    db <- dbConnect(SQLite(), filename)
    df <- dbGetQuery(db, query)
    dbDisconnect(db)
    df
}

load_prepared_query <- function(filename, query, params)
{
    db <- dbConnect(SQLite(), filename)
    df <- dbGetPreparedQuery(db, query, params)
    dbDisconnect(db)
    df
}

load_coexistence <- function(db_filename, n_bootstraps, frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df_filename <- paste(db_filename, sprintf('-coexistence-%d-%0.2f-%0.2f-%0.2f.Rds', n_bootstraps, frac_res_min, frac_res_max, frac_res_increase_threshold), sep='')
    #print(df_filename)
    if(file.exists(df_filename)) {
        return(readRDS(df_filename))
    }
    
    #print(db_filename)
    db <- dbConnect(SQLite(), db_filename)
    
    costs <- dbGetQuery(db, 'SELECT DISTINCT cost FROM summary_overall ORDER BY cost')$cost
    treatments <- dbGetQuery(db, 'SELECT DISTINCT treatment_multiplier FROM summary_overall ORDER BY treatment_multiplier')$treatment_multiplier
    
    gamma_ratios <- dbGetQuery(db, 'SELECT DISTINCT gamma_treated_ratio_resistant_to_sensitive FROM summary_overall ORDER BY gamma_treated_ratio_resistant_to_sensitive')$gamma_treated_ratio_resistant_to_sensitive
    
    df <- NULL
    for(cost in costs) {
        for(gamma_ratio in gamma_ratios) {
            query <- 'SELECT frac_resistant FROM summary_overall WHERE treatment_multiplier = ? AND cost = ? AND gamma_treated_ratio_resistant_to_sensitive = ?'
            frac_res_05 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = treatments[2], cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            frac_res_10 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = treatments[3], cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            frac_res_15 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = treatments[4], cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            
            stopifnot(
                length(frac_res_05) == length(frac_res_10) &&
                length(frac_res_10) == length(frac_res_15)
            )
            n_runs <- length(frac_res_05)
            
            frac_res_bs_05 <- matrix(sample(frac_res_05, n_runs * n_bootstraps, replace = TRUE), ncol = n_runs)
            frac_res_bs_10 <- matrix(sample(frac_res_10, n_runs * n_bootstraps, replace = TRUE), ncol = n_runs)
            frac_res_bs_15 <- matrix(sample(frac_res_15, n_runs * n_bootstraps, replace = TRUE), ncol = n_runs)
            
            above_min <- (frac_res_bs_05 >= frac_res_min) & (frac_res_10 >= frac_res_min) & (frac_res_15 >= frac_res_min)
            below_max <- (frac_res_bs_05 <= frac_res_max) & (frac_res_10 <= frac_res_max) & (frac_res_15 <= frac_res_max)
            sufficient_increase <- (frac_res_bs_15 / frac_res_bs_05) >= frac_res_increase_threshold
            
            matches_coexistence_criteria <- above_min & below_max & sufficient_increase
            p_coexistence <- apply(matches_coexistence_criteria, 1, mean)
            stopifnot(length(p_coexistence) == n_bootstraps)
            
            df <- rbind(df, data.frame(
                cost = cost,
                gamma_treated_ratio_resistant_to_sensitive = gamma_ratio,
                p_coexistence_mean = mean(p_coexistence),
                p_coexistence_se = sd(p_coexistence),
                p_coexistence_025 = quantile(p_coexistence, 0.025),
                p_coexistence_975 = quantile(p_coexistence, 0.975)
            ))
        }
    }
    dbDisconnect(db)
    
    saveRDS(df, df_filename)
    
    df
}
