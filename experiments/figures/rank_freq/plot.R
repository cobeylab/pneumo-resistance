#!/usr/bin/env Rscript

# Panel A: rank-frequency curve by serotype for <5 y (color one),
# rank-frequency curve by serotype for >= 20 y, with the null model, treatment multiplier = 0, cost = 2%

# Panel B: rank-frequency curve by serotype for <5 y (color one)
# rank-frequency curve by serotype for >= 20 y, with the null model, treatment multiplier = 1, cost = 2%

# Panel C: rank-frequency curve by serotype for <5 y (color one)
# rank-frequency curve by serotype for >= 20 y, with the AAM+AST model, treatment multiplier = 1, cost = 2%


library(RSQLite)
library(ggplot2)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365
N_AGECLASSES <- 3

main <- function()
{
    generate_plot('model0-null', 0)
    generate_plot('model0-null', 1)
    generate_plot('model15-aam+ast', 1)
    
    invisible()
}

generate_plot <- function(model_name, tm)
{
    db_filename <- sprintf('../../%s/cost_duration/sweep_db-summaries.sqlite', model_name)
    db <- dbConnect(SQLite(), db_filename)
    df <- dbGetPreparedQuery(db,
        'SELECT * FROM summary_by_serotype_ageclass
            WHERE treatment_multiplier = ? AND cost = 0.98
            AND (ageclass = 0 OR ageclass = 2)
        ;',
        data.frame(treatment_multiplier = tm)
    )
    print(df)
    dbDisconnect(db)
    
    p <- ggplot(data = df) +
        geom_boxplot(aes(
            x = factor(serotype_id + 1), y = freq_avg,
            color = factor(ageclass)
        ), size = 0.1, outlier.size = 0.05) +
        #geom_point(aes(
        #    x = factor(serotype_id + 1), y = freq_avg,
        #    color = factor(ageclass)
        #), position = position_jitterdodge(), size = 0.1) +
        xlab('Serotype by rank in carriage duration') +
        ylab('Frequency') + 
        scale_y_continuous(limits = c(0, 0.3)) +
        theme_minimal() +
        theme(
            axis.title.x = element_text(size = 8),
            axis.title.y = element_text(size = 8),
            axis.text = element_text(size = 8)
        )
    
    ggsave(
        sprintf('rank_freq_box-%s-treat=%.1f.pdf', model_name, tm),
        p, width = 6, height = 2
    )
}

printf <- function(...)
{
    cat(sprintf(...))
}

main()
