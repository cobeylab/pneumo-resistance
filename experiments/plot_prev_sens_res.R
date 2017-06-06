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
    
    tm_vec <- dbGetQuery(db, 'SELECT DISTINCT treatment_multiplier FROM summary_by_ageclass')$treatment_multiplier
    print(tm_vec)
    gr_vec <- dbGetQuery(db, 'SELECT DISTINCT gamma_treated_ratio_resistant_to_sensitive AS gr FROM summary_by_ageclass')$gr
    print(gr_vec)
    ageclass_vec <- dbGetQuery(db, 'SELECT DISTINCT ageclass FROM summary_by_ageclass')$ageclass
    print(ageclass_vec)
    cost_vec <- dbGetQuery(db, 'SELECT DISTINCT cost FROM summary_by_ageclass')$cost
    print(cost_vec)
    
    dir.create('prevalence_by_resistance')
    for(cost in cost_vec) {
        for(gr in gr_vec) {
            plot_prevalence_by_treatment(cost, gr, db, dir_name)
        }
    }
    
    dbDisconnect(db)
    
    invisible()
}

plot_prevalence_by_treatment <- function(cost, gr, db, dir_name)
{
    df <- dbGetPreparedQuery(db, 'SELECT * FROM summary_by_ageclass WHERE cost = ? AND gamma_treated_ratio_resistant_to_sensitive = ?', data.frame(cost, gr))
    
    df$ageclass_name <- factor(sapply(df$ageclass, function(ac) { AGECLASS_NAMES[ac + 1] }), levels = AGECLASS_NAMES)
    
    print(colnames(df))
    p <- ggplot(data = df) +
        facet_grid(. ~ ageclass_name) +
        geom_point(aes(x = treatment_multiplier, y = prev_res), color = 'blue') +
        geom_point(aes(x = treatment_multiplier, y = prev_sens), color = 'red') +
        theme_minimal()
    
    ggsave(
        file.path(
            dir_name,
            'prevalence_by_resistance',
            sprintf('gamma_ratio=%.2f-cost=%.2f.pdf', gr, cost)
        ), p, width = 7, height = 7
    )
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
