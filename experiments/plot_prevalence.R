#!/usr/bin/env Rscript

library(RSQLite)
library(ggplot2)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365

main <- function()
{
    args <- commandArgs(trailingOnly = TRUE)
    for(db_filename in args) {
        print(db_filename)
        tryCatch( { run_for_filename(db_filename) }, error = function(e) {} )
    }
}

run_for_filename <- function(db_filename)
{
    dir_name <- dirname(db_filename)
    db <- dbConnect(SQLite(), db_filename)
    df <- dbGetQuery(db, 'SELECT * FROM summary_overall')
    dbDisconnect(db)
    
    plot_prevalence_by_treatment(df, dir_name)
    
    invisible()
}

plot_prevalence_by_treatment <- function(df, dir_name)
{
    print(colnames(df))
    
    p <- ggplot(data = df) +
        facet_grid(cost ~ gamma_treated_ratio_resistant_to_sensitive) +
        geom_point(aes(x = treatment_multiplier, y = prevalence), size = 0.1) +
        xlab('treatment multiplier') +
        ylab('prevalence') +
        theme_minimal() +
        theme(axis.text.x = element_text(size=6)) +
        theme(axis.text.y = element_text(size=8))
    
    ggsave(file.path(dir_name, 'prev_overall_by_treatment.pdf'), p, width = 6, height = 8)
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
