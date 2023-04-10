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
import re
import datetime

DATE_RE = ".*(\d{8}).*"
 
def merge_datasets(num_classes, paths, fname_str, out_dir, base_index = 0, data = None, qual = None): 
    for root, dirs, files in os.walk(paths[base_index]):
        for fle in files:
            if fname_str in fle:
                fname = os.path.join(out_dir, fle)
                dqi_fname = os.path.splitext(fname)[0] + ".DQI.tif"
                if os.path.exists(fname):
                    continue
                fle1 = os.path.join(root, fle)
                dat1 = gdal.Open(fle1)
                if data is None:
                    tmp = dat1.ReadAsArray()
                    imgData1 = np.zeros(tmp.shape) - 1
                else:
                    imgData1 = data
                    tmp = dat1.ReadAsArray()
                if qual is None:
                    dqi = np.zeros(imgData1.shape) - 1
                else:
                    dqi = qual
                inds = np.where((imgData1 < 0) & (tmp >= 0))
                tmp[inds] = imgData1[inds]
                imgData1 = tmp 
                #print(imgData1.max(), num_classes**(len(paths)-(1+base_index)))
                #imgData1[inds] = imgData1[inds] #+ num_classes**(len(paths)-(1+base_index))

                dqi[inds] = base_index                
                for j in range(base_index+1, len(paths)):
                    fle2 = os.path.join(paths[j], fle)
                    if os.path.exists(fle2):
                        dat2 = gdal.Open(fle2)
                        imgData2 = dat2.ReadAsArray()
                        inds = np.where((imgData1 < 0) & (imgData2 >= 0))
                        imgData1[inds] = imgData2[inds] #+ num_classes**(len(paths)-(1+j))
                        dqi[inds] = j
                        #inds = np.where((imgData1 % num_classes == 0) & (imgData2 > 0))
                        #imgData1[inds] = imgData2[inds] + num_classes**(len(paths)-(1+j))
                        #inds = np.where((imgData1 % num_classes == 0))
                        #imgData1[inds] = 0
                        dat2.FlushCache()
                        dat2 = None
                
                nx = imgData1.shape[1]
                ny = imgData1.shape[0]
                print(imgData1.min(), imgData1.max(), dqi.min(), dqi.max())
                geoTransform = dat1.GetGeoTransform()
                wkt = dat1.GetProjection()
                dat1.FlushCache()
                dat1 = None
          
                out_ds = gdal.GetDriverByName("GTiff").Create(fname, nx, ny, 1, gdal.GDT_Int16)
                out_ds.SetGeoTransform(geoTransform)
                out_ds.SetProjection(wkt)
                out_ds.GetRasterBand(1).WriteArray(imgData1)
                out_ds.FlushCache()
                out_ds = None
                data = imgData1        
  
                out_ds = gdal.GetDriverByName("GTiff").Create(dqi_fname, nx, ny, 1, gdal.GDT_Int16)
                out_ds.SetGeoTransform(geoTransform)
                out_ds.SetProjection(wkt)
                out_ds.GetRasterBand(1).WriteArray(dqi)
                out_ds.FlushCache()
                out_ds = None
                qual = dqi                 

    return data, qual


#assumes rename to having date in filename
def merge_monthly(dirname, max_dqi, max_class):

    monthlies = {}

    for root, dirs, files in os.walk(dirname):
        for fle in files:
            mtch = re.search(DATE_RE, fle)
            if mtch:
                dte = datetime.datetime.strptime(mtch.group(1), "%Y%m%d")
                if dte.month in monthlies.keys():
                    monthlies[dte.month].append([dte, os.path.join(root, fle)])
                else:
                    monthlies[dte.month] = [[dte, os.path.join(root, fle)]]

    for mnth in monthlies.keys():
        newImgData = None
        newDqi = None
        dat = None
        for i in range(0, max_dqi):
            for k in range(max_class,0,-1):
                for j in range(0, len(monthlies[mnth])):
                    dat = gdal.Open(monthlies[mnth][j][1]) 
                    imgData = dat.ReadAsArray()
 
                    if newImgData is None:
                        newImgData = np.zeros(imgData.shape) - 1
                        newDqi = np.zeros(imgData.shape) - 1

                    
                    inds = np.where((imgData == k) & (k > newImgData) & ((newDqi == -1) | ((newDqi > -1) & (i < newDqi)))) 
                    newDqi[inds] = i
                    newImgData[inds] = k
          
        nx = newImgData.shape[1]
        ny = newImgData.shape[0]
        geoTransform = dat.GetGeoTransform()
        wkt = dat.GetProjection()
        dat.FlushCache()
        dat = None

        out_ds = gdal.GetDriverByName("GTiff").Create(os.path.join(dirname, monthlies[mnth][0][0].strftime("%Y%m") + "_karenia_brevis.Monthly.tif"), nx, ny, 1, gdal.GDT_Byte)
        out_ds.SetGeoTransform(geoTransform)
        out_ds.SetProjection(wkt)
        out_ds.GetRasterBand(1).WriteArray(newImgData)
        out_ds.FlushCache()
        out_ds = None
            
        out_ds = gdal.GetDriverByName("GTiff").Create(os.path.join(dirname, monthlies[mnth][0][0].strftime("%Y%m") + "_karenia_brevis.Monthly.DQI.tif"), nx, ny, 1, gdal.GDT_Byte)
        out_ds.SetGeoTransform(geoTransform)
        out_ds.SetProjection(wkt)
        out_ds.GetRasterBand(1).WriteArray(newDqi)
        out_ds.FlushCache()
        out_ds = None    



def main(yml_fpath):

    #Translate config to dictionary 
    yml_conf = read_yaml(yml_fpath)
    #Run 
    data = None
    qual = None
 
    if yml_conf["gen_daily"]:
        for i in range(len(yml_conf['input_paths'])):
            data, qual = merge_datasets(yml_conf['num_classes'], yml_conf['input_paths'], 
                yml_conf['fname_str'], yml_conf['out_dir'], i, data, qual)
    if yml_conf["gen_monthly"]:
        merge_monthly(yml_conf['dirname'], yml_conf['max_dqi'], yml_conf['max_class'])  
 

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-y", "--yaml", help="YAML file for fusion info.")
    args = parser.parse_args()
    main(args.yaml)
