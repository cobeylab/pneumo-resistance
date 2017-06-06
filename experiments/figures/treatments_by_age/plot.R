#!/usr/bin/env Rscript

library(rjson)
library(ggplot2)

YEARS <- 50
N_SEROTYPES <- 25
T_YEAR <- 365
N_AGECLASSES <- 3

main <- function()
{
    ntreat_by_age <- load_json('../../../parameters/mean_n_treatments_per_age_empirical_usa.json')
    
    p <- ggplot(data = data.frame(age = 0:(length(ntreat_by_age) - 1), n_treatments = ntreat_by_age)) +
        geom_line(aes(x = age, y = n_treatments)) +
        xlab('Age') +
        ylab('Mean treatments per year') +
        scale_y_continuous(limits = c(0, 1.5)) +
        theme_minimal()
    
    ggsave(
        'treatments_by_age.pdf', p, width = 4, height = 3
    )
    invisible()
}

printf <- function(...)
{
    cat(sprintf(...))
}

load_json <- function(filename)
{
    conn <- file(filename, 'r')
    lines <- readLines(conn)
    close(conn)
    
    return(fromJSON(paste(lines, sep='\n')))
}

main()
