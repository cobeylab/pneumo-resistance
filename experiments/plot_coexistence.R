#!/usr/bin/env Rscript

library(RSQLite)
library(ggplot2)

#MODEL_NAMES <- c('a-null', 'b-aam', 'c-ast', 'd-std', 'e-aam+ast', 'f-aam+std', 'g-ast+std', 'h-aam+ast+std')

MODEL_NAMES <- c(
    'model0-null',
    'model1-age-assortative',
    'model2-age-specific-treatment',
    'model3-short-treatment',
    'model4-cotransmission',
    'model5-pseudospatial-immigration',
    'model6-combined-1245',
    'model7-psi+aam+ast+ct+eih',
    'model8-psi+ct+eih',
    'model9-psi+aam+ast',
    'model10-psi+st',
    'model11-psi+ast',
    'model12-psi+aam'
)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365
N_AGECLASSES <- 3
AGECLASS_NAMES <- c('0 - 5', '5 - 20', '20 - 111')

N_BOOTSTRAPS <- 1000
FRAC_RES_MIN_VALS <- c(0.02)
FRAC_RES_MAX_VALS <- c(0.50, 0.98)
FRAC_RES_INCREASE_THRESHOLD_VALS <- c(1.6)

main <- function()
{
    args <- commandArgs(trailingOnly = TRUE)
    if(length(args) == 0) {
        root_dir <- '.'
    }
    else {
        root_dir <- args[1]
    }
    
    for(frac_res_min in FRAC_RES_MIN_VALS) {
        for(frac_res_max in FRAC_RES_MAX_VALS) {
            for(frac_res_thresh in FRAC_RES_INCREASE_THRESHOLD_VALS) {
                run(root_dir, frac_res_min, frac_res_max, frac_res_thresh)
            }
        }
    }
    
    invisible()
}

run <- function(root_dir, frac_res_min, frac_res_max, frac_res_thresh)
{
    df <- data.frame(
        model = factor(levels = MODEL_NAMES),
        cost_type = factor(levels = c('duration', 'transmission')),
        cost = numeric(0), gamma_treated_ratio_resistant_to_sensitive = numeric(0), coexistence_rate = numeric(0)
    )
    for(model_name in MODEL_NAMES) {
        try(
            {
                for(cost_type in c('duration', 'transmission')) {
                    df <- rbind(
                        df,
                        process_model(
<<<<<<< HEAD
                            root_dir, model_name, cost_type, FRAC_RES_MIN, FRAC_RES_MAX, FRAC_RES_INCREASE_THRESHOLD
=======
                            root_dir, model_name, cost_type, frac_res_min, frac_res_max, frac_res_thresh
>>>>>>> 8c207896185bdf985d1b60a7c9de212b98516814
                        )
                    )
                }
            }
        )
    }
    
    df_filename <- file.path(
        root_dir,
        sprintf('coexistence-min=%.2f-max=%.2f-thresh=%.1f.csv', frac_res_min, frac_res_max, frac_res_thresh)
    )
    write.csv(df, df_filename)
    
    p <- ggplot(data = df) +
        facet_grid(model ~ cost_type) +
        geom_tile(aes(fill = coexistence_rate, x = factor(gamma_treated_ratio_resistant_to_sensitive), y = factor(cost)))
    
    ggsave(
        file.path(
            root_dir, sprintf('coexistence-min=%.2f-max=%.2f-thresh=%.1f.pdf', frac_res_min, frac_res_max, frac_res_thresh)
        ),
        p, width = 7, height = 28
    )
}

process_model <- function(root_dir, model_name, cost_type, frac_res_min, frac_res_max, frac_res_thresh)
{
    df <- data.frame(
        model = factor(levels = MODEL_NAMES),
        cost_type = factor(levels = c('duration', 'transmission')),
        cost = numeric(0), gamma_treated_ratio_resistant_to_sensitive = numeric(0), coexistence_rate = numeric(0)
    )
    
    db_filename <- file.path(root_dir, model_name, sprintf('cost_%s', cost_type), 'sweep_db-summaries.sqlite')
    if(!file.exists(db_filename)) {
        return(df);
    }
    printf('%s\n', db_filename)
    db <- dbConnect(SQLite(), db_filename)
    
    costs <- dbGetQuery(db, 'SELECT DISTINCT cost FROM summary_overall ORDER BY cost')$cost
    treatments <- dbGetQuery(db, 'SELECT DISTINCT treatment_multiplier FROM summary_overall ORDER BY treatment_multiplier')$treatment_multiplier
    gamma_ratios <- dbGetQuery(db, 'SELECT DISTINCT gamma_treated_ratio_resistant_to_sensitive FROM summary_overall ORDER BY gamma_treated_ratio_resistant_to_sensitive')$gamma_treated_ratio_resistant_to_sensitive
    
    for(cost in costs) {
        for(gamma_ratio in gamma_ratios) {
            query <- 'SELECT frac_resistant FROM summary_overall WHERE treatment_multiplier = ? AND cost = ? AND gamma_treated_ratio_resistant_to_sensitive = ?'
            frac_res_05 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = 0.5, cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            frac_res_10 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = 1.0, cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            frac_res_15 <- dbGetPreparedQuery(db, query, data.frame(
                treatment_multiplier = 1.5, cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio
            ))$frac_resistant
            
            frac_res_bs <- matrix(0, nrow=N_BOOTSTRAPS, ncol=3)
            frac_res_bs_05 <- sample(frac_res_05, N_BOOTSTRAPS, replace = TRUE)
            frac_res_bs_10 <- sample(frac_res_10, N_BOOTSTRAPS, replace = TRUE)
            frac_res_bs_15 <- sample(frac_res_15, N_BOOTSTRAPS, replace = TRUE)
            
            above_min <- (frac_res_bs_05 >= frac_res_min) & (frac_res_10 >= frac_res_min) & (frac_res_15 >= frac_res_min)
            below_max <- (frac_res_bs_05 <= frac_res_max) & (frac_res_10 <= frac_res_max) & (frac_res_15 <= frac_res_max)
            sufficient_increase <- (frac_res_bs_15 / frac_res_bs_05) >= frac_res_thresh
            
            matches_coexistence_criteria <- above_min & below_max & sufficient_increase
            
            df <- rbind(df, data.frame(
                model = model_name,
                cost_type = cost_type,
                cost = cost, gamma_treated_ratio_resistant_to_sensitive = gamma_ratio, coexistence_rate = mean(matches_coexistence_criteria)
            ))
        }
    }
    dbDisconnect(db)
    
    df_filename <- file.path(
        root_dir, model_name, sprintf('cost_%s', cost_type),
        sprintf('coexistence-min=%.2f-max=%.2f-thresh=%.1f.csv', frac_res_min, frac_res_max, frac_res_thresh)
    )
    write.csv(df, df_filename)
    df
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
