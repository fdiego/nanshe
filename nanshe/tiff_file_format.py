__author__ = "John Kirkham <kirkhamj@janelia.hhmi.org>"
__date__ = "$Jun 26, 2014 11:40:54 EDT$"


import glob
import os
import collections

import numpy
import h5py

import vigra
import vigra.impex
import pathHelpers

import advanced_debugging
import additional_generators
import additional_io
import expanded_numpy



# Get the logger
logger = advanced_debugging.logging.getLogger(__name__)



@advanced_debugging.log_call(logger)
def get_multipage_tiff_shape_dtype(new_tiff_filename):
    """
        Gets the info about the shape (including page number as time) and dtype.

        Args:
            new_tiff_filename(str):             the TIFF file to get info about

        Returns:
            (collections.OrderedDict):          an ordered dictionary with "shape" first and "dtype" (type) second.
    """

    shape_dtype_result = collections.OrderedDict([("shape" , None), ("dtype" , None)])

    new_tiff_file_info = vigra.impex.ImageInfo(new_tiff_filename)
    new_tiff_file_number_pages = vigra.impex.numberImages(new_tiff_filename)

    new_tiff_file_shape = new_tiff_file_info.getShape()
    shape_dtype_result["shape"] = new_tiff_file_shape[:-1] + (new_tiff_file_number_pages,) + new_tiff_file_shape[-1:]

    shape_dtype_result["dtype"] = new_tiff_file_info.getDtype()

    return(shape_dtype_result)


@advanced_debugging.log_call(logger)
def get_multipage_tiff_shape_dtype_transformed(new_tiff_filename, axis_order = "zyxtc", pages_to_channel = 1):
    """
        Gets the info about the shape and dtype after some transformations have been performed .

        Args:
            new_tiff_filename(str):             the TIFF file to get info about
            axis_order(str):                    the desired axis order when reshaped
            pages_to_channel(int):              number of channels to divide from the pages

        Returns:
            (collections.OrderedDict):          an ordered dictionary with "shape" first and "dtype" (type) second.
    """

    assert(pages_to_channel > 0)
    assert(len(axis_order) == 5)
    assert(all([_ in axis_order for _ in "zyxtc"]))

    new_tiff_file_shape, new_tiff_file_dtype = get_multipage_tiff_shape_dtype(new_tiff_filename).values()

    # Correct if the tiff is missing dims by adding singletons
    if (len(new_tiff_file_shape) == 5):
        pass
    elif (len(new_tiff_file_shape) == 4):
        new_tiff_file_shape = (1,) + new_tiff_file_shape
    else:
        raise Exception("Invalid dimensionality for TIFF. Found shape to be \"" + repr(new_tiff_file_shape) + "\".")

    # Correct if some pages are for different channels
    if (pages_to_channel != 1):
        new_tiff_file_shape = new_tiff_file_shape[:-2] + (new_tiff_file_shape[-2] / pages_to_channel, pages_to_channel * new_tiff_file_shape[-1],)

    # Correct the axis order
    if (axis_order != "zyxtc"):
        vigra_ordering = dict(additional_generators.reverse_each_element(enumerate("zyxtc")))

        new_tiff_file_shape_transposed = []
        for each_axis_label in axis_order:
            new_tiff_file_shape_transposed.append(new_tiff_file_shape[vigra_ordering[each_axis_label]])

        new_tiff_file_shape = tuple(new_tiff_file_shape_transposed)

    shape_dtype_result = collections.OrderedDict([("shape" , None), ("dtype" , None)])

    shape_dtype_result["shape"] = new_tiff_file_shape
    shape_dtype_result["dtype"] = new_tiff_file_dtype

    return(shape_dtype_result)


@advanced_debugging.log_call(logger)
def get_standard_tiff_array(new_tiff_filename, axis_order = "tzyxc", pages_to_channel = 1):
    """
        Reads a tiff file and returns a standard 5D array.

        Args:
            new_tiff_filename(str):             the TIFF file to read in

            axis_order(int):                    how to order the axes (by default returns "tzyxc").

            pages_to_channel(int):              if channels are not normally stored in the channel variable, but are
                                                stored as pages (or as a mixture), then this will split neighboring
                                                pages into separate channels. (by default is 1 so changes nothing)

        Returns:
            (numpy.ndarray):                    an array with the axis order specified.
    """

    assert(pages_to_channel > 0)

    # Get the shape and dtype information
    shape, dtype = get_multipage_tiff_shape_dtype(new_tiff_filename).values()

    # Turn dtype into something that VIGRA's readImage or readVolume will take
    dtype_str = ""
    if dtype is None:
        dtype_str = ""
    elif (dtype is numpy.float64) or (dtype is float):
        dtype_str = "DOUBLE"
    elif (dtype is numpy.float32):
        dtype_str = "FLOAT"
    elif (dtype is numpy.uint32):
        dtype_str = "UINT32"
    elif (dtype is numpy.int32):
        dtype_str = "INT32"
    elif (dtype is numpy.uint16):
        dtype_str = "UINT16"
    elif (dtype is numpy.int16):
        dtype_str = "INT16"
    elif (dtype is numpy.uint8):
        dtype_str = "UINT8"
    else:
        raise Exception("Unacceptable dtype of " + repr(dtype))

    if shape[-2] > 1:
        # Our algorithm expect double precision
        new_tiff_array = vigra.impex.readVolume(new_tiff_filename, dtype = dtype_str)
        # Convert to normal array
        new_tiff_array = new_tiff_array.view(numpy.ndarray)
    else:
        # Our algorithm expect double precision
        new_tiff_array = vigra.impex.readImage(new_tiff_filename, dtype = dtype_str)
        # Convert to normal array
        new_tiff_array = new_tiff_array.view(numpy.ndarray)
        # Need to add singleton time dimension before channel
        new_tiff_array = expanded_numpy.add_singleton_axis_pos(new_tiff_array, -2)

    # Check to make sure the dimensions are ok
    if (new_tiff_array.ndim == 5):
        pass
    elif (new_tiff_array.ndim == 4):
        # Has no z. So, add this.
        new_tiff_array = expanded_numpy.add_singleton_axis_beginning(new_tiff_array)
    else:
        raise Exception("Invalid dimensionality for TIFF. Found shape to be \"" + repr(new_tiff_array.shape) + "\".")

    # Some people use pages to hold time and channel data. So, we need to restructure it.
    # However, if they are properly structuring their TIFF file, then they shouldn't incur a penalty.
    if pages_to_channel > 1:
        new_tiff_array = new_tiff_array.reshape(new_tiff_array.shape[:-2] + (new_tiff_array.shape[-2] / pages_to_channel, pages_to_channel * new_tiff_array.shape[-1],))

    new_tiff_array = expanded_numpy.tagging_reorder_array(new_tiff_array,
                                                          from_axis_order = "zyxtc",
                                                          to_axis_order = axis_order,
                                                          to_copy = True)

    return(new_tiff_array)


@advanced_debugging.log_call(logger)
def convert_tiffs(new_tiff_filenames, new_hdf5_pathname, axis = 0, channel = 0, z_index = 0, pages_to_channel = 1):
    """
        Convert a stack of tiffs to an HDF5 file.

        Args:
            new_tiff_filenames(list or str):    takes a str for a single file or a list of strs for filenames to combine
                                                (allows regex).

            new_hdf5_pathname(str):             the HDF5 file and location to store the dataset.

            axis(int):                          which axis to concatenate along.

            channel(int):                       which channel to select for the HDF5 (can only keep one).

            pages_to_channel(int):              if channels are not normally stored in the channel variable, but are
                                                stored as pages, then this will split neighboring pages into separate
                                                channels.
    """

    assert(pages_to_channel > 0)

    # Get the axes that do not change
    static_axes = numpy.array(list(additional_generators.xrange_with_skip(3, to_skip = axis)))

    # if it is only a single str, make it a singleton list
    if isinstance(new_tiff_filenames, str):
        new_tiff_filenames = [new_tiff_filenames]

    # Expand any regex in path names
    new_tiff_filenames = additional_io.expand_pathname_list(*new_tiff_filenames)

    # Determine the shape and dtype to use for the dataset (so that everything will fit).
    new_hdf5_dataset_shape = numpy.zeros((3,), dtype = int)
    new_hdf5_dataset_dtype = bool
    for each_new_tiff_filename in new_tiff_filenames:
        each_new_tiff_file_shape, each_new_tiff_file_dtype = get_multipage_tiff_shape_dtype_transformed(each_new_tiff_filename,
                                                                                                        axis_order = "cztyx",
                                                                                                        pages_to_channel = pages_to_channel).values()
        each_new_tiff_file_shape = each_new_tiff_file_shape[2:]

        # Find the increase on the merge axis. Find the largest shape for the rest.
        each_new_tiff_file_shape = numpy.array(each_new_tiff_file_shape)
        new_hdf5_dataset_shape[axis] += each_new_tiff_file_shape[axis]
        new_hdf5_dataset_shape[static_axes] = numpy.array([new_hdf5_dataset_shape[static_axes], each_new_tiff_file_shape[static_axes]]).max(axis=0)

        # Finds the best type that everything can be cast to without loss of precision.
        if not numpy.can_cast(each_new_tiff_file_dtype, new_hdf5_dataset_dtype):
            if numpy.can_cast(new_hdf5_dataset_dtype, each_new_tiff_file_dtype):
                new_hdf5_dataset_dtype = each_new_tiff_file_dtype
            else:
                raise Exception("Cannot find safe conversion between new_hdf5_dataset_dtype = " + repr(new_hdf5_dataset_dtype) + " and each_new_tiff_file_dtype = " + repr(each_new_tiff_file_dtype) + ".")

    # Convert to standard forms
    new_hdf5_dataset_shape = tuple(new_hdf5_dataset_shape)
    new_hdf5_dataset_dtype = numpy.dtype(new_hdf5_dataset_dtype)

    # Get all the needed locations for the HDF5 file and dataset
    new_hdf5_path_components = pathHelpers.PathComponents(new_hdf5_pathname)
    new_hdf5_filename = new_hdf5_path_components.externalPath
    new_hdf5_groupname = new_hdf5_path_components.internalDirectory
    new_hdf5_dataset_name = new_hdf5_path_components.internalPath

    # Dump all datasets to the file
    with h5py.File(new_hdf5_filename, "a") as new_hdf5_file:
        if new_hdf5_groupname not in new_hdf5_file:
            new_hdf5_file.create_group(new_hdf5_groupname)

        new_hdf5_group = new_hdf5_file[new_hdf5_groupname]
        new_hdf5_dataset = new_hdf5_group.create_dataset(new_hdf5_dataset_name,
                                                         new_hdf5_dataset_shape,
                                                         new_hdf5_dataset_dtype)

        new_hdf5_dataset_axis_pos = 0
        for each_new_tiff_filename in new_tiff_filenames:
            # Read the data in the format specified.
            each_new_tiff_array = get_standard_tiff_array(each_new_tiff_filename,
                                                          axis_order = "cztyx",
                                                          pages_to_channel = pages_to_channel)

            # Take channel and z selection
            # TODO: Could we drop the channel constraint by saving different channels to different arrays? Need to think about it.
            # TODO: Want to drop z constraint, but need to consult with Ferran about algorithms that work on 3D for the end.
            each_new_tiff_array = each_new_tiff_array[channel, z_index]

            # Store into the current slice and go to the next one.
            new_hdf5_dataset_axis_pos_next = new_hdf5_dataset_axis_pos + len(each_new_tiff_array)
            new_hdf5_dataset[ new_hdf5_dataset_axis_pos : new_hdf5_dataset_axis_pos_next ] = each_new_tiff_array
            new_hdf5_dataset_axis_pos = new_hdf5_dataset_axis_pos_next
