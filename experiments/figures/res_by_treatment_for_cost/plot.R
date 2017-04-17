#!/usr/bin/env Rscript

# Plot fraction resistant by treatment for null model (& defaults for all plots)
# Show for treatment=0, 0.5., 1, 1.5 (if time, might be nice to add more treatment levels).
# Box-and-whisker w/ superimposed raw points might be good option, but we can experiment. 
# gamma_treated is 5
# 

# **Notes for all plots**
# Please express fitness cost as percent (0%, 2%,... instead of $\xi$ = 1, 0.98,...).
# Please make eps or ps. Default is gamma_ratio = 5, but this should be adjustable.

library(RSQLite)
library(ggplot2)

source('../shared.R')

main <- function()
{
    df <- load_prepared_query(
        '../../model0-null/cost_duration/sweep_db-summaries.sqlite',
        'SELECT * FROM summary_overall WHERE gamma_treated_ratio_resistant_to_sensitive = ?;',
        data.frame(gamma_treated_ratio_resistant_to_sensitive = GAMMA_RATIO)
    )
    df$cost_pct <- factor(
        sapply(
            df$cost,
            function(cost) { sprintf('%d%%', 100 - as.integer(cost * 100)) }
        ),
        levels = c('0%', '2%', '4%', '6%', '8%', '10%')
    )
    
    goossens <- read.csv('../Goossens_rough.csv')
    
    # p <- ggplot(df, aes(factor(treatment_multiplier), frac_resistant, color = factor(cost))) +
    #     geom_boxplot()
    # ggsave('res_by_treatment_for_cost_boxplot.pdf', p, width = 6, height = 4)
    # 
    # p2 <- ggplot(df, aes(factor(treatment_multiplier), frac_resistant, color = factor(cost))) +
    #     geom_point(position = position_jitterdodge(), size = 0.5)
    # ggsave('res_by_treatment_for_cost_jitter.pdf', p2, width = 6, height = 4)
    
    #theme_set(theme_grey(base_size = 9))
    p3 <- ggplot() +
        geom_boxplot(
            data = df,
            aes(factor(treatment_multiplier), frac_resistant, color = cost_pct),
            outlier.alpha = 0
        ) +
        geom_point(
            data = df,
            aes(factor(treatment_multiplier), frac_resistant, color = cost_pct),
            position = position_jitterdodge(), size = 0.5
        ) +
        labs(x = 'Treatment', y = 'Fraction resistant', color = 'Cost') +
        geom_point(
            data = goossens, aes(1 + (treatment * 2), fraction_resistant), shape = 18, color = 'gray'
        ) +
        theme_minimal(base_size = 9)
        
    save_all_formats('res_by_treatment_for_cost', p3, width = 3.5, height = 2)
    
    # p <- ggplot() +
    #     geom_boxplot(
    #         data = df,
    #         aes(
    #             factor(treatment_multiplier),
    #             frac_resistant,
    #             color = cost_pct
    #         )
    #     ) +
    #     geom_point(data = goossens, aes(1 + (treatment * 2), fraction_resistant)) +
    #     geom_point(data = data.frame(x = c(0, 1, 2, 3, 4, 5), y = c(0, 0, 0, 0, 0, 0)), aes(x, y), color = 'red', size = 5)
    # ggsave('res_by_treatment_for_cost.pdf', p, width = 6, height = 4)
}

main()
