#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import copy

import numpy


def read_file(file_path, trial_start_zone, custom_fields=None, delimiter=None):
    
    # Check whether the file exists.
    if not os.path.isfile(file_path):
        raise Exception("File not found at specified path: {}".format( \
            file_path))
    
    # Check whether the file is of the right type.
    fname = os.path.basename(file_path)
    name, ext = os.path.splitext(fname)
    ext = ext.lower()
    if ext not in [".tsv", ".csv", ".txt"]:
        raise Exception("File {} was not recognised".format(fname) + \
            " as a delimiter-separated file. Its extension is" + \
            " {}, but '.csv', '.tsv', or '.txt' was expected.".format(ext))
    
    # Set the delimiter.
    if (delimiter is None) or (delimiter == "auto"):
        if ext == ".csv":
            delimiter = ","
        elif ext == ".tsv":
            delimiter = "\t"
    
    # Open the file.
    with open(file_path, "r") as f:
        # Snif out the dialect. We're using a large chunk of data for this,
        # as the header gets quite big.
        dialect = csv.Sniffer().sniff(f.read(10240))
        # Check the delimiter.
        if delimiter is None:
            print("Auto-detected delimiter: '{}'".format( \
                dialect.delimiter))
        else:
            if dialect.delimiter != delimiter:
                print("Detected delimiter '{}'".format(dialect.delimiter) + \
                    ", but overwriting with specified delimiter" + \
                    " '{}'".format(delimiter))
            else:
                print("Using delimiter: '{}'".format( \
                    dialect.delimiter))
                
        # Set the reading position back to the start of the file.
        f.seek(0)
        # Start a CSV reader.
        reader = csv.reader(f, dialect)
        
        # Read the file header.
        header = next(reader)
        len_header = len(header)
        
        # Get the default fields.
        iparticipant = header.index("Participant Private ID")
        iresolution = header.index("Participant Monitor Size")
        iviewport = header.index("Participant Viewport Size")
        izone = header.index("Zone Name")
        iresp = header.index("Response")
        itime = header.index("Reaction Onset")
        
        # Find the custom fields.
        if custom_fields is None:
            custom_fields = []
        ifields = {}
        for field in custom_fields:
            if field not in header:
                raise Exception("Custom field '{}' does not".format(field) + \
                    "appear in the file header.")
            else:
                ifields[field] = header.index(field)
        
        # Create an empty structure for the data.
        data = {}
        
        # Loop through all lines.
        current_participant = None
        for i, line in enumerate(reader):
            
            # Check if the line is the expected length.
            if len(line) != len_header:
                continue
            
            # Check the participant number.
            if line[iparticipant] != current_participant:
                # Create new participant.
                current_participant = copy.copy(line[iparticipant])
                data[current_participant] = { \
                    "trials":[], \
                    "resolution":line[iresolution], \
                    "viewport":line[iviewport], \
                    }

            # Update the trial.
            if line[izone] == trial_start_zone:
                # Create new trial.
                data[current_participant]["trials"].append({ \
                    "msg":[], \
                    "time":[], \
                    "x":[], \
                    "y":[], \
                    })
                # Add the custom field data.
                for field in custom_fields:
                    data[current_participant]["trials"][-1]["msg"].append( \
                        [field, line[ifields[field]]])
            
            # Only record if a trial has started.
            if len(data[current_participant]["trials"]) > 0:

                # Add new coordinates to the time, x, and y fields.
                if line[izone] == "coordinate":
                    # Read the time.
                    data[current_participant]["trials"][-1]["time"].append(\
                        float(line[itime]))
                    # Read and split the coordinates.
                    x, y = line[iresp].split(" ")
                    # Add it to the list
                    data[current_participant]["trials"][-1]["x"].append(x)
                    data[current_participant]["trials"][-1]["y"].append(y)
                # Add any other data to the messages.
                else:
                    data[current_participant]["trials"][-1]["msg"].append( \
                        [line[izone], line[iresp]])
        
    # Convert all data lists to NumPy arrays.
    for participant in data.keys():
        for i in range(len(data[participant]["trials"])):
            for key in ["time", "x", "y"]:
                data[participant]["trials"][i][key] = numpy.array( \
                    data[participant]["trials"][i][key], dtype=float)
    
    return data


