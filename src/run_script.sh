#!/bin/bash

# Set the arguments
manual_seed_values=("1" "2" "5")
num_support_val_values=("1" "2" "3" "4" "6" "9")
# num_support_val_values=("1" "2")
# Original list
original_list=(0 1 3 5 6 7 9 10 12 17)
# Loop for four times
for iteration in {1..4}; do
    echo "Iteration $iteration:"
# Shuffle the list
shuffled_list=($(shuf -e "${original_list[@]}"))

# Select the first three elements
p1=${shuffled_list[0]}
p2=${shuffled_list[1]}
p3=${shuffled_list[2]}

# Loop over manual_seed values
for seed in "${manual_seed_values[@]}"; do
    # Loop over num_support_val values
    for num_support in "${num_support_val_values[@]}"; do
        # Run the Python script with the given arguments
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p1" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p2" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p3" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p1" "$p2" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p1" "$p3" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p2" "$p3" --excluded_patients "$p1" "$p2" "$p3"
        python few_shot_train.py --manual_seed "$seed" --num_support_val "$num_support" --patients "$p1" "$p2" "$p3" --excluded_patients "$p1" "$p2" "$p3"
    done

done

done
