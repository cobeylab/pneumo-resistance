#!/usr/bin/env Rscript

library(RSQLite)
library(ggplot2)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365
N_AGECLASSES <- 3
AGECLASS_NAMES <- c('0 - 5', '5 - 20', '20 - 111')

main <- function()
{
    args <- commandArgs(trailingOnly = TRUE)
    if(length(args) != 1) {
        stop('Must provide sweep database as only argument.')
    }
    
    db_filename <- args[1]
    dir_name <- dirname(db_filename)
    db <- dbConnect(SQLite(), db_filename)
    df_by_ageclass <- dbGetQuery(db, 'SELECT * FROM summary_by_ageclass')
    df_by_serotype <- dbGetQuery(db, 'SELECT * FROM summary_by_serotype')
    dbDisconnect(db)
    
    #print(df_by_ageclass)
    #print(df_by_serotype)
    
    # Plots fraction resistant against treatment multiplier for different parameter values.
    # plot_all_by_treatment(db, 'res_by_treatment', start_year, end_year, cost_param_name)
    
    plot_resistance_by_treatment(df_by_ageclass, dir_name)
    plot_prevalence_by_treatment(df_by_ageclass, dir_name)
    
    # Plots fraction resistant against serotype rank.
    plot_resistance_by_serotype(df_by_serotype, dir_name)
    
    
    invisible()
}

plot_resistance_by_treatment <- function(df, dir_name)
{
    df$ageclass_name <- factor(sapply(df$ageclass, function(ac) { AGECLASS_NAMES[ac + 1] }), levels = AGECLASS_NAMES)
    
    print(colnames(df))
    
    p <- ggplot(data = df) +
        facet_grid(cost ~ gamma_treated_ratio_resistant_to_sensitive * ageclass_name) +
        geom_point(aes(x = treatment_multiplier, y = frac_resistant))
    
    ggsave(file.path(dir_name, 'res_by_treatment.pdf'), p, width = 14, height = 14)
}

plot_prevalence_by_treatment <- function(df, dir_name)
{
    df$ageclass_name <- factor(sapply(df$ageclass, function(ac) { AGECLASS_NAMES[ac + 1] }), levels = AGECLASS_NAMES)
    
    print(colnames(df))
    
    p <- ggplot(data = df) +
        facet_grid(cost ~ gamma_treated_ratio_resistant_to_sensitive * ageclass_name) +
        geom_point(aes(x = treatment_multiplier, y = prevalence))
    
    ggsave(file.path(dir_name, 'prev_by_treatment.pdf'), p, width = 14, height = 14)
}

plot_resistance_by_serotype <- function(df, dir_name)
{
    print(colnames(df))
    
    p <- ggplot(data = df) +
        facet_grid(cost ~ gamma_treated_ratio_resistant_to_sensitive * treatment_multiplier) +
        geom_point(aes(x = serotype_id, y = frac_resistant))
    
    ggsave(file.path(dir_name, 'res_by_rank.pdf'), p, width = 14, height = 14)
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
