#!/usr/bin/env Rscript

# (new figure) Bar plot has select models across x axis and two y axes:
# (1) fitness cost at which coexistence most likely,
# (2) average fraction of simulations (across all costs) that support coexistence.
# Models are null (model0), aam (model1), ast (model2), psi (model5), cotrans (model4--is this ct+eih?),
# aam+ast+psi (model9), and ast+aam+psi+ct+eih (model7). 
# 
# It should be possible to generate this figure for different coexistence definitions.
# The one I'm doing now is 0.02-0.98 with a >=1.1 increase.
# 
# I don't have a name/label for this figure yet. Will add one when I do.

library(RSQLite)
library(ggplot2)
library(dplyr)

source('../shared.R')

MODELS <- list(
    list(label = 'Null', dirname = 'model0-null/cost_duration'),
    list(label = 'AAM', dirname = 'model1-aam/cost_duration'),
    list(label = 'AST', dirname = 'model2-ast/cost_duration'),
    list(label = 'AAM+AST', dirname = 'model15-aam+ast/cost_duration'),
    list(label = 'PSI', dirname = 'model5-psi/cost_duration'),
    list(label = 'AAM+AST+PSI', dirname='model9-psi+aam+ast/cost_duration'),
    list(label = 'CT-EIC', dirname = 'model4-ct/cost_duration'),
    list(label = 'CT-EIH', dirname= 'model16-ct-eih/cost_duration'),
    list(label = 'CT-EIC+AAM+AST+PSI', dirname = 'model6-aam+ast+ct+psi/cost_duration'),
    list(label = 'CT-EIH+AAM+AST+PSI',dirname = 'model7-psi+aam+ast+ct+eih/cost_duration'),
#    list(label = '2.5 d (CT-EIH+AAM+AST+PSI)', dirname='model17-treat=2.5-aam+ast+ct-eih+psi/cost_duration'),
    list(label = '5 d (CT-EIH+AAM+AST+PSI)', dirname='model13-treat=5-aam+ast+ct-eih+psi/cost_duration'),
#    list(label = '10 d', dirname='model7-psi+aam+ast+ct+eih/cost_duration'),
    list(label = '20 d (CT-EIH+AAM+AST+PSI)', dirname='model14-treat=20-aam+ast+ct-eih+psi/cost_duration'),
#    list(label = 'Null (dur)', dirname = 'model0-null/cost_duration'),
    list(label = 'Null (trans)', dirname = 'model0-null/cost_transmission'),
#    list(label = 'AAM+AST+PSI (dur)', dirname='model9-psi+aam+ast/cost_duration'),
    list(label = 'AAM+AST+PSI (trans)', dirname='model9-psi+aam+ast/cost_transmission'),
#    list(dirname = 'model16-ct-eih/cost_duration', label = 'CT-EIH (dur)'),
    list(dirname = 'model16-ct-eih/cost_transmission', label = 'CT-EIH (trans)')
)

main <- function()
{
    plot_by_cost(0.02, 0.6, 1.1)
    plot_by_cost(0.02, 0.98, 1.1)
}

plot_by_cost <- function(frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df <- load_data_by_cost(MODELS, frac_res_min, frac_res_max, frac_res_increase_threshold)
    df$cost_discrete <- factor(round(100 * (1.0 - df$cost)), levels = c(0, 2, 4, 6, 8, 10))
    print(df$cost_discrete)
    df$p_coexistence_label <- sapply(df$p_coexistence_mean, function(cr) {
        return(sprintf('%.2f', cr))
    })
    print(df$p_coexistence_label)
    
    p <- ggplot(
            data = df,
            aes(
                fill = p_coexistence_mean,
                x = factor(gamma_treated_ratio_resistant_to_sensitive),
                y = factor(cost_discrete),
                label = p_coexistence_label
            )
        ) +
        geom_tile() +
        facet_wrap(~model, ncol = 3, scales = 'free') +
        geom_text(color = 'lightgray', size=2.5) +
        scale_y_discrete(labels = c('0%', '2%', '4%', '6%', '8%', '10%')) +
        labs(x = 'Ratio', y = 'Cost', fill = 'P(Coexistence)') +
        theme_minimal(base_size=9)
    
    save_all_formats(
        sprintf('coexistence-%.2f-%.2f-%.1f', frac_res_min, frac_res_max, frac_res_increase_threshold),
        p, width = 6.5, height = 9.5
    )
}

load_data_by_cost <- function(model_list, frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df <- NULL
    model_num <- 0
    models <- character(0)
    for(model_spec in model_list) {
        df_i <- load_coexistence(
            file.path('..', '..', model_spec$dirname, 'sweep_db-summaries.sqlite'),
            N_BOOTSTRAPS, frac_res_min, frac_res_max, frac_res_increase_threshold
        )
        df_i$model_num <- model_num
        df_i$model <- model_spec$label
        
        df <- rbind(df, df_i)
        models <- c(models, model_spec$label)
        model_num <- model_num + 1
    }
    df$model <- factor(df$model, levels = models)
    df
}

main()
