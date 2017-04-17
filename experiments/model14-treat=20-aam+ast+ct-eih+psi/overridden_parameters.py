use_random_mixing = False
alpha = 'polymod'
mean_n_treatments_per_age = 'empirical_usa'
transmission_model = 'cotransmission'
transmission_scaling = 'by_host'
immigration_resistance_model = 'fraction_resistant_by_serotype'
p_immigration_resistant_bounds = [0.01, 0.99]
p_immigration_resistant = 0.01 # Only used when # colonizations == 0

treatment_duration_mean = 20.0
