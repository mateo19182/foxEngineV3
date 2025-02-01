#!/bin/bash

source env/bin/activate
python user_manager.py add admin admin
python user_manager.py test_data
