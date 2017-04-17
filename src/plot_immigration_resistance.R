#!/usr/bin/env Rscript

library(ggplot2)
library(RSQLite)

main <- function()
{
    conn <- dbConnect(SQLite(), 'output_db.sqlite')
    
    df <- dbGetQuery(conn, 'SELECT * FROM immigration_resistance')
    
    p <- ggplot(data = df) +
        facet_grid(serotype_id ~ .) +
        geom_line(aes(x = t, y = p_immigration_resistant))
    ggsave('immigration_resistance.pdf', p, width=12, height=18)
    
    invisible()
}

main()
