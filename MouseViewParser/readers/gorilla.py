#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import copy
import time

import numpy

import openpyxl

# This is a number caster that can deal with NaN values. It should replace
# the openpyxl number caster, which tries to cast NaNs as int, and thus
# results in ValueError exceptions.
def _cast_number_or_nan(value):
    "Convert numbers as string to an int or float"
    if value == "NaN" or value == "nan" or value == "NA":
        return float(value)
    if "." in value or "E" in value or "e" in value:
        return float(value)
    return int(value)

# Only overwrite the number caster if a number caster exists. (It was not a
# part of earlier versions).
import openpyxl.worksheet
if hasattr(openpyxl.worksheet, "_reader"):
    # Overwrite the openpyxl number caster, because it chokes on NaNs.
    openpyxl.worksheet._reader._cast_number = _cast_number_or_nan


def read_file(file_path, trial_folder_path, custom_fields=None, \
    use_public_id=False, verbose=False):
    
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
    
    # Open the file.
    t0 = time.time()
    with open(file_path, "r") as f:
        # Snif out the dialect. We're using a large chunk of data for this,
        # as the header gets quite big.
        dialect = csv.Sniffer().sniff(f.read(10240))
        # Check the delimiter.
        if verbose:
            print("Auto-detected delimiter: '{}'".format( \
                dialect.delimiter))
                
        # Set the reading position back to the start of the file.
        f.seek(0)
        # Start a CSV reader.
        reader = csv.reader(f, dialect)
        
        # Read the file header.
        header = next(reader)
        len_header = len(header)
        
        # Get the default fields.
        ipublic = header.index("Participant Public ID")
        iprivate = header.index("Participant Private ID")
        if use_public_id:
            iparticipant = ipublic
        else:
            iparticipant = iprivate
        iresolution = header.index("Participant Monitor Size")
        iviewport = header.index("Participant Viewport Size")
        itrial = header.index("Trial Number")
        izone = header.index("Zone Type")
        iresp = header.index("Response")
        
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
                if verbose:
                    print("Row {} is of the wrong number ".format(i+1) + \
                        "of cells (expected {}). ".format(len_header) + \
                        "Its content is:\n{}".format(line))
                continue
            
            # Check the participant number.
            if line[iparticipant] != current_participant:
                # Create new participant.
                current_participant = copy.copy(line[iparticipant])
                data[current_participant] = { \
                    "trials":[], \
                    "resolution":line[iresolution], \
                    "viewport":line[iviewport], \
                    "public_id":line[ipublic], \
                    "private_id":line[iprivate], \
                    }
                if verbose:
                    print("{}: Reading ".format(round(time.time()-t0,3)) + \
                        "participant {}".format(current_participant))
            
            # Get the trial number.
            trial_nr = line[itrial]
            
            # Check if this is a MouseView line, and if the reported file is
            # local (we need) or online (we ignore). The zone type should be
            # "mouse_view", but let's add in a view options in case this
            # changes in the future.
            if line[izone] in ["mouse_view", "mouseview", "MouseView"]:

                # Skip lines with a URL file path.
                if line[iresp][:8] == "https://":
                    continue

                # Get the file name, and construct the path to the local file.
                fname = line[iresp]
                file_path = os.path.join(trial_folder_path, fname)
                # Load the data, if it exists.
#                if verbose:
#                    print("Loading file {}".format(file_path))
                if os.path.isfile(file_path):
                    participant, viewport, trial = \
                        read_single_trial_file(file_path, verbose=verbose)
                # Use an empty trial if the file cannot be found.
                else:
                    if verbose:
                        print("Participant {} ".format(current_participant) + \
                            "trial {} could not be found.".format(trial_nr) + \
                            "\nMissing file: {}".format(file_path))
                    trial = { \
                        "msg":[], \
                        "time":numpy.array([], dtype=numpy.float32), \
                        "x":numpy.array([], dtype=numpy.float32), \
                        "y":numpy.array([], dtype=numpy.float32), \
                        }
                # Add the custom fields.
                for field in custom_fields:
                    trial["msg"].insert(0, [field, line[ifields[field]]])
                
                # Double-check that this is the same participant. (If not:
                # something went wrong in the Gorilla file, as the file name
                # comes from there! Or someone messed with either the OG file
                # or the trial file names...)
                if str(participant) != line[iprivate]:
                    raise Exception("File {} is listed for ".format(fname) + \
                        "participant {}, ".format(current_participant) + \
                        "but the file itself reports to be from " + \
                        "participant {}".format(participant))
                
                # Add the trial to the current participant.
                data[current_participant]["trials"].append(trial)

    # Convert all data lists to NumPy arrays.
    for participant in data.keys():
        for i in range(len(data[participant]["trials"])):
            for key in ["time", "x", "y"]:
                data[participant]["trials"][i][key] = numpy.array( \
                    data[participant]["trials"][i][key], dtype=float)
    
    return data

    
def read_folder(folder_path, verbose=False):
    
    # Check whether the folder exists.
    if not os.path.isdir(folder_path):
        raise Exception("Folder not found at specified path: {}".format( \
            folder_path))
    
    # Create an empty structure for the data. This will hold all participants
    # (each with their own key), and under each participant it will have keys
    # for trials (list of all trials, each is their own dict structure), 
    # viewport (automatically read from file), resolution (not actually in the 
    # files, so simply a copy of viewport; it's here for backwards
    # compatibility), and participant_id (copy of the initial key name, but
    # included in case the key name is changed).
    data = {}
    
    # Read all the files in the folder.
    all_files = os.listdir(folder_path)
    # Sort alphabetically (this makes .
    all_files.sort()
    # Count all the files.
    n_files = len(all_files)
    
    # Loop through all files.
    for fi, fname in enumerate(all_files):
    
        # Construct the file path.
        file_path = os.path.join(folder_path, fname)
        # Split name and extension from the full name.
        name, ext = os.path.splitext(fname)

        # Skip lock files.
        if name[:2] == "~$":
            continue
        # Check whether the file is of the right type.
        ext = ext.lower()
        if ext not in [".xls", ".xlsx"]:
            if verbose:
                print("File {} was not recognised as an MS ".format(fname) + \
                    "Excel file. Its extension is '{}', but ".format(ext) + \
                    "'.xls' or '.xlsx' was expected.")
            continue
        
        if verbose:
            print("Reading file '{}' ({}/{})".format(fname, fi+1, n_files))
        
        # Load the data.
        current_participant, viewport, trial = read_single_trial_file( \
            file_path, verbose=verbose)
        
        # Create a new entry for the current participant, if the ID is new.
        if current_participant not in data.keys():
            # Add a new entry for the current participant.
            data[current_participant] = { \
                "trials":[], \
                "resolution":None, \
                "viewport":None, \
                }
        
        # Store the viewport data (copy to resolution, as we do not know what
        # the resolution is from just the single-trial data).
        if data[current_participant]["viewport"] is None:
            data[current_participant]["viewport"] = copy.deepcopy(viewport)
            data[current_participant]["resolution"] = copy.deepcopy(viewport)
        
        # Store the trial data.
        data[current_participant]["trials"].append(copy.deepcopy(trial))

    # Convert all data lists to NumPy arrays.
    for participant in data.keys():
        for i in range(len(data[participant]["trials"])):
            for key in ["time", "x", "y"]:
                data[participant]["trials"][i][key] = numpy.array( \
                    data[participant]["trials"][i][key], dtype=numpy.float32)
    
    return data


def read_single_trial_file(file_path, custom_fields=None, verbose=False):
    
    # Open the file using openpyxl.
    workbook = openpyxl.load_workbook(file_path, read_only=True, \
        data_only=True)
    # Get the active sheet (this is the first one, which should be the
    # only one in the Gorilla output).
    sheet = workbook.active

    # Store the values for the current trial in this trial dict.
    trial = { \
        "msg":[], \
        "time":[], \
        "x":[], \
        "y":[], \
        }
    
    # Loop through all the rows, and parse them as necessary.
    current_participant = None
    viewport = None
    for i, row in enumerate(sheet.iter_rows()):

        # Get the first row as the header.
        if i == 0:
            # Get the header.
            header = [cell.value for cell in row]
            # Count the number of columns in the file.
            len_header = len(header)
            # Get the index numbers for important rows. (We do this once, to
            # avoid having to call "index" on each iteration.)
            iparticipant = header.index("participant_id")
            itype = header.index("type")
            izone = header.index("zone_name")
            ihor = header.index("zone_x")
            iver = header.index("zone_y")
            iwidth = header.index("zone_width")
            iheight = header.index("zone_height")
            itime = header.index("time_stamp")
            ix = header.index("x")
            iy = header.index("y")
            # Skip to the next line in the file.
            continue
        
        # Check if the line is the expected length.
        if len(row) != len_header:
            if verbose:
                print("\tRow {} is of the wrong number ".format(i+1) + \
                    "of cells (expected {}). ".format(len_header) + \
                    "Its content is:\n\t{}".format(\
                    str([cell.value for cell in row])))
            continue
        
        # Get the participant ID.
        if current_participant is None:
            # Get the current participant ID.
            current_participant = row[iparticipant].value
        
        # First, check if this row is for MouseView coordinates.
        if row[itype].value == "mouseview":
            
            # Parse the MouseView coordinates.
            trial["time"].append(float(row[itime].value))
            trial["x"].append(float(row[ix].value))
            trial["y"].append(float(row[iy].value))
        
        # Process rows that are NOT MouseView coordinates.
        else:
            # Add the row as a message.
            t = float(row[itime].value)
            msg = \
                "type={};zone={};zone_x={};zone_y={};zone_w={};zone_h={}" \
                .format(row[itype].value, row[izone].value, \
                row[ihor].value, row[iver].value, row[iwidth].value, \
                row[iheight].value)
            trial["msg"].append((t, msg))
            
            # If this row has zone name "screen", use it to get the screen
            # width and height. This is the viewport, but because there is
            # no additional information on the resolution, we will also copy
            # copy the viewrect into the "resolution" field. This is for 
            # backwards compatibility.
            if row[itype].value == "zone":
                if row[izone].value == "screen":
                    w = row[iwidth].value
                    h = row[iheight].value
                    viewport = "{}x{}".format(w, h)
    
    return current_participant, viewport, trial
