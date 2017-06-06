#!/usr/bin/env Rscript

library(RSQLite)
library(ggplot2)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365
N_AGECLASSES <- 3

main <- function()
{
    db_filename <- '../../model9-psi+aam+ast/cost_duration/sweep_db-summaries.sqlite'
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
    
    plot_prevalence_by_treatment(0.96, 4, db)
    
    dbDisconnect(db)
    
    invisible()
}

plot_prevalence_by_treatment <- function(cost, gr, db)
{
    df <- dbGetPreparedQuery(db, 'SELECT * FROM summary_by_ageclass WHERE cost = ? AND gamma_treated_ratio_resistant_to_sensitive = ?', data.frame(cost, gr))
    
    df1 <- df
    df1$resistant <- factor('sensitive', levels = c('sensitive', 'resistant'))
    df1$prev <- df1$prev_sens
    df2 <- df
    df2$resistant <- factor('resistant', levels = c('sensitive', 'resistant'))
    df2$prev <- df2$prev_res
    
    df <- rbind(df1, df2)
    
    print(colnames(df))
    
    p <- ggplot(data = df) +
        facet_grid(
            . ~ ageclass,
            labeller = labeller(
                ageclass = c(`0` = '[0, 5)', `1` = '[5, 20)', `2` = '[20, inf)')
            )
        ) +
        geom_boxplot(
            aes(factor(treatment_multiplier), prev, color = resistant),
            outlier.alpha = 0
        ) +
        geom_point(
            data = df,
            aes(factor(treatment_multiplier), prev, color = resistant),
            position = position_jitterdodge(), size = 0.25
        ) +
        xlab('treatment multiplier') +
        ylab('prevalence') +
        theme_minimal()
    
    ggsave(
        sprintf('gamma_ratio=%.2f-cost=%.2f.pdf', gr, cost), p, width = 6, height = 2
    )
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
