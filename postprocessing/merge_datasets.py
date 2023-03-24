"""
Copyright [2022-23], by the California Institute of Technology and Chapman University. 
ALL RIGHTS RESERVED. United States Government Sponsorship acknowledged. Any commercial use must be negotiated with the 
Office of Technology Transfer at the California Institute of Technology and Chapman University.
This software may be subject to U.S. export control laws. By accepting this software, the user agrees to comply with all 
applicable U.S. export laws and regulations. User has the responsibility to obtain export licenses, or other export authority as may be 
required before exporting such information to foreign countries or providing access to foreign persons.
"""

import numpy as np
from utils import numpy_to_torch, read_yaml, insitu_hab_to_tif
from osgeo import gdal, osr
import argparse
import os
from pandas import DataFrame as df
from skimage.util import view_as_windows
from copy import deepcopy


 
def merge_datasets(paths, fname_str, out_dir): 
    for root, dirs, files in os.walk(paths[0]):
        for fle in files:
            if fname_str in fle:
                fle1 = os.path.join(root, fle)
                dat1 = gdal.Open(fle1)
                imgData1 = dat1.ReadAsArray()
                inds = np.where(imgData1 >= 0)
                imgData1[inds] = imgData1[inds] + 2**(len(paths)-1)


                for j in range(1, len(paths)):
                    fle2 = os.path.join(paths[j], fle)
                    dat2 = gdal.Open(fle2)
                    imgData2 = dat2.ReadAsArray()
                    inds = np.where((imgData1 < 0) & (imgData2 >= 0))
                    imgData1[inds] = imgData2[inds] + 2**(len(paths)-(1+j))
                    dat2.FlushCache()
                    dat2 = None
                
                nx = imgData1.shape[1]
                ny = imgData1.shape[0]
                geoTransform = dat1.GetGeoTransform()
                wkt = dat1.GetProjection()
                dat1.FlushCache()
                dat1 = None
          
                fname = os.path.join(out_dir, fle)
                out_ds = gdal.GetDriverByName("GTiff").Create(fname, nx, ny, 1, gdal.GDT_Byte)
                out_ds.SetGeoTransform(geoTransform)
                out_ds.SetProjection(wkt)
                out_ds.GetRasterBand(1).WriteArray(imgData1)
                out_ds.FlushCache()
                out_ds = None

def main(yml_fpath):

    #Translate config to dictionary 
    yml_conf = read_yaml(yml_fpath)
    #Run 
    merge_datasets(yml_conf['input_paths'], yml_conf['fname_str'], yml_conf['out_dir'])


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-y", "--yaml", help="YAML file for fusion info.")
    args = parser.parse_args()
    main(args.yaml)
