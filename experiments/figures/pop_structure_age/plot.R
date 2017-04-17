#!/usr/bin/env Rscript

library(RSQLite)
library(ggplot2)
library(dplyr)

source('../shared.R')

MODELS <- list(
    list(label = 'Null', dirname = 'model0-null/cost_duration'),
    list(label = 'AAM', dirname = 'model1-aam/cost_duration'),
    list(label = 'AST', dirname = 'model2-ast/cost_duration'),
    list(label = 'AAM+AST+PSI', dirname='model9-psi+aam+ast/cost_duration')
)

main <- function()
{
    df <- load_data(MODELS)
    
    df_summ <- df %>% group_by(model, ageclass_name) %>% summarise(
        frac_resistant_mean = mean(frac_resistant),
        frac_resistant_sd = sd(frac_resistant)
    )
    print(df_summ)
    
    p <- ggplot(data = df_summ, aes(model, frac_resistant_mean)) +
        geom_bar(stat = 'identity', aes(fill = ageclass_name), position = position_dodge()) +
        geom_errorbar(
            aes(
                color = ageclass_name,
                ymin = frac_resistant_mean - frac_resistant_sd, ymax = frac_resistant_mean + frac_resistant_sd
            ),
            width = 0.4,
            position = position_dodge(width = 0.9),
            show.legend = FALSE
        ) +
        theme_minimal(base_size=9) +
        scale_fill_grey(start=0.8, end=0.2) +
        scale_color_manual(values = c('black', 'black')) +
        labs(x='',y = 'Fraction resistant', fill = 'Age (y)')
    
    save_all_formats('pop_structure_age', p, width = 4, height = 2)
}

load_data <- function(model_list)
{
    df <- NULL
    model_levels <- NULL
    for(model_spec in model_list) {
        print(model_spec)
        df_i <- load_prepared_query(
            file.path('..', '..', model_spec$dirname, 'sweep_db-summaries.sqlite'),
            'SELECT * FROM summary_by_ageclass
            WHERE gamma_treated_ratio_resistant_to_sensitive = ? AND (ageclass = 0 OR ageclass = 2)
            AND cost = 0.98 AND treatment_multiplier = 1',
            data.frame(gamma_treated_ratio_resistant_to_sensitive = GAMMA_RATIO)
        )
        print(head(df_i))
        df_i$model <- model_spec$label
        model_levels <- c(model_levels, model_spec$label)
        
        if(is.null(df)) {
            df <- df_i
        }
        else {
            df <- rbind(df, df_i)
        }
    }
    df$model <- factor(df$model, levels = model_levels)
    df$ageclass_name <- factor(sapply(df$ageclass, function(ac) {
        if(ac == 0) {
            return('0-5')
        }
        else if(ac == 2) {
            return('>20')
        }
        else {
            stop('invalid ageclass')
        }
    }), levels = c('0-5', '>20'))
    df
}

main()
