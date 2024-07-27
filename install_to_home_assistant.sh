#!/bin/bash
# Script that installs aio_energy_management (latest from master) into Home Assistant
git clone https://github.com/kotope/aio_energy_management aio_energy_management_git
mv aio_energy_management_git/custom_components/aio_energy_management .
rm -rf aio_energy_management_git