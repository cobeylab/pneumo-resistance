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
    df <- load_data(MODELS_ALL)
    
    df$treatment_multiplier[df$model == 'ST+AAM+AST+CT-EIH+PSI'] <- df$treatment_multiplier[df$model ==	'ST+AAM+AST+CT-EIH+PSI'] / 2
    df$treatment_multiplier[df$model == 'LT+AAM+AST+CT-EIH+PSI'] <- df$treatment_multiplier[df$model ==	'LT+AAM+AST+CT-EIH+PSI'] * 2
    
    p <- ggplot(
            data = df,
            aes(treatment_multiplier, frac_resistant, color = cost_pct)
        ) +
        geom_jitter(size = 0.5) +
        facet_grid(
            model ~ gamma_treated_ratio_resistant_to_sensitive,
            # model ~ gamma_treated_ratio_resistant_to_sensitive,
            labeller = labeller(
                #model_num = function(value) {
                #   return(sprintf('model %d', as.integer(value)))
                #},
                 model = function(value) {
                     return(value)
                 },
                gamma_treated_ratio_resistant_to_sensitive = function(value) {
                    return(sprintf('ratio = %d', as.integer(value)))
                }
            ),
	    scales = 'free_x'
        ) +
        theme_minimal(base_size=8) +
        labs(x = 'Treatment', y = 'Fraction resistant', color = 'Cost') +
        theme(
            axis.text.x = element_text(size = 6),
            axis.text.y = element_text(size = 6),
            strip.text.x = element_text(size = 6)
        )
    save_all_formats('supp_res_by_treatment', p, width = 6.5, height = 9.5)
}

load_data <- function(model_list)
{
    df <- NULL
    model_num <- 0
    models <- character(0)
    for(model_spec in model_list) {
        df_i <- load_query(
            file.path('..', '..', model_spec$dirname, 'sweep_db-summaries.sqlite'),
            'SELECT * FROM summary_by_ageclass
            WHERE ageclass = 0'
        )
        df_i$model_num <- model_num
        df_i$model <- model_spec$label
        
        if(is.null(df)) {
            df <- df_i
        }
        else {
            df <- rbind(df, df_i)
        }
        models <- c(models, model_spec$label)
        model_num <- model_num + 1
    }
    df$cost_pct <- factor(
        sapply(
            df$cost,
            function(cost) { sprintf('%d%%', 100 - as.integer(cost * 100)) }
        ),
        levels = c('0%', '2%', '4%', '6%', '8%', '10%')
    )
    df$model <- factor(df$model, levels = models)
    df
}

main()
