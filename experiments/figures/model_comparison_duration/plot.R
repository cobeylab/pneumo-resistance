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
    list(label = '2.5 d', dirname = 'model17-treat=2.5-aam+ast+ct-eih+psi/cost_duration'),
    list(label = '5 d', dirname = 'model13-treat=5-aam+ast+ct-eih+psi/cost_duration'),
    list(label = '10 d', dirname = 'model7-psi+aam+ast+ct+eih/cost_duration'),
    list(label = '20 d', dirname = 'model14-treat=20-aam+ast+ct-eih+psi/cost_duration')
)

main <- function()
{
    plot_by_cost(0.02, 0.98, 1.1)
    plot_across_cost(0.02, 0.98, 1.1)
}

plot_by_cost <- function(frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df <- load_data_by_cost(MODELS, frac_res_min, frac_res_max, frac_res_increase_threshold)
    print(colnames(df))
    df$cost_discrete <- factor(round(100 * (1.0 - df$cost)), levels = c(0, 2, 4, 6, 8, 10))
    
    p <- ggplot(data = df, aes(model, p_coexistence_mean, fill = cost_discrete)) +
        geom_bar(stat = 'identity', position = 'dodge') +
        geom_errorbar(
            aes(
                #ymin = p_coexistence_mean - p_coexistence_se, ymax = p_coexistence_mean + p_coexistence_se,
                ymin = p_coexistence_025, ymax = p_coexistence_975,
                color = cost_discrete
            ),
            width = 0.4,
            position = position_dodge(width = 0.9),
            color = 'gray'
        ) +
        labs(x = '', y = 'Probability of coexistence', fill = 'Cost') +
        scale_fill_discrete(labels = c('0%', '2%', '4%', '6%', '8%', '10%') ) +
        theme_minimal(base_size=9)

    save_all_formats(
        sprintf('model_comp_duration_bycost-%.2f-%.2f-%.1f', frac_res_min, frac_res_max, frac_res_increase_threshold),
        p, 4, 2
    )
}

plot_across_cost <- function(frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df <- load_data_across_cost(MODELS, frac_res_min, frac_res_max, frac_res_increase_threshold)
    
    # p <- ggplot(
    #     data = df,
    #     aes(model, mean_coexistence_rate)
    # ) +
    #     scale_y_continuous(labels = scales::percent) +
    #     geom_bar(stat = 'identity') +
    #     theme_minimal(base_size=9) +
    #     labs(x = '', y = 'Probability of coexistence')
    # save_all_formats(
    #     sprintf('model_comp_acrosscost-%.2f-%.2f-%.1f', frac_res_min, frac_res_max, frac_res_increase_threshold),
    #     p, 4, 2
    # )
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
    
    df[df$gamma_treated_ratio_resistant_to_sensitive == GAMMA_RATIO,]
}

load_data_across_cost <- function(model_list, frac_res_min, frac_res_max, frac_res_increase_threshold)
{
    df <- NULL
    model_num <- 0
    models <- character(0)
    for(model_spec in model_list) {
        df_i <- identify_best_cost(load_coexistence(
            file.path('..', '..', model_spec$dirname, 'sweep_db-summaries.sqlite'),
            N_BOOTSTRAPS, frac_res_min, frac_res_max, frac_res_increase_threshold
        ))
        df_i$model_num <- model_num
        df_i$model <- model_spec$label
        
        df <- rbind(df, df_i)
        models <- c(models, model_spec$label)
        model_num <- model_num + 1
    }
    df$model <- factor(df$model, levels = models)
    df
}

identify_best_cost <- function(df_in) {
    df_in <- df_in[df_in$gamma_treated_ratio_resistant_to_sensitive == GAMMA_RATIO,]
    df_out <- data.frame(
        best_cost = df_in$cost[which.max(df_in$p_coexistence_mean)],
        best_coexistence_rate = max(df_in$p_coexistence_mean),
        mean_coexistence_rate = mean(df_in$p_coexistence_mean),
        sd_coexistence_rate = sd(df_in$p_coexistence_mean)
    )
    print(df_out)
    df_out
}

main()
