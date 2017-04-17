#!/usr/bin/env Rscript

# Plot fraction resistant by serotypes for different ranks, model7, treatment=1, kids 0-5, all costs

# (fig:res_by_rank_for_cost) -- like current Fig. 3
# 
# It would be nice to see box-whisker variants too. Fitness cost should be a percent.
# (Would be good to keep color scales consistent among plots.)
# Would also be nice if script could take models and treatment as arguments (will always show kids).

# **Notes for all plots**
# Please express fitness cost as percent (0%, 2%,... instead of $\xi$ = 1, 0.98,...).
# Please make eps or ps. Default is gamma_ratio = 5, but this should be adjustable.

library(RSQLite)
library(ggplot2)

source('../shared.R')

main <- function()
{
    df <- load_prepared_query(
        '../../model7-psi+aam+ast+ct+eih/cost_duration/sweep_db-summaries.sqlite',
        'SELECT * FROM summary_by_serotype
            WHERE gamma_treated_ratio_resistant_to_sensitive = ?
	    AND treatment_multiplier = 1.0
        ;',
        data.frame(gamma_treated_ratio_resistant_to_sensitive = 4)
    )
    df$cost_pct <- factor(
        sapply(
            df$cost,
            function(cost) { sprintf('%d%%', 100 - as.integer(cost * 100)) }
        ),
        levels = c('0%', '2%', '4%', '6%', '8%', '10%')
    )
    
    # POINTS
    p <- ggplot() +
        geom_point(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            size = 0.5
        ) +
        labs(x = 'Serotype rank', y = 'Fraction resistant', color = 'Cost') +
        theme_minimal()
    save_all_formats('res_by_rank_for_cost-points', p, width = 6, height = 4)
    
    # BOXPLOT
    p <- ggplot() +
        geom_boxplot(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            outlier.size = 0.5
        ) +
        labs(x = 'Serotype rank', y = 'Fraction resistant', color = 'Cost') +
        theme_minimal()
    save_all_formats('res_by_rank_for_cost-boxplot', p, width = 12, height = 4)
    
    # BOXPLOT + POINTS
    p <- ggplot() +
        geom_boxplot(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            outlier.alpha = 0
        ) +
        geom_point(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            position = position_jitterdodge(), size = 0.5
        ) +
        labs(x = 'Serotype rank', y = 'Fraction resistant', color = 'Cost') +
        theme_minimal()
    save_all_formats('res_by_rank_for_cost-boxplot+points', p, width = 12, height = 4)
    
    # BOXPLOT + POINTS BY COST
    p <- ggplot() +
        geom_boxplot(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            outlier.alpha = 0
        ) +
        geom_point(
            data = df,
            aes(factor(serotype_id + 1), frac_resistant, color = cost_pct),
            position = position_jitterdodge(), size = 0.5
        ) +
        facet_grid(cost_pct ~ .)
        labs(x = 'Serotype rank', y = 'Fraction resistant', color = 'Cost') +
        theme_minimal()
        save_all_formats('res_by_rank_for_cost-boxplot+points-facet', p, width = 10, height = 16)
}

main()
