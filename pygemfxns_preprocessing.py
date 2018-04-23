"""
pygemfxns_preprocessing.py is a list of the model functions that are used to preprocess the data into the proper format.

"""
#========== IMPORT MODULES USED IN FUNCTIONS ==========================================================================
import pandas as pd
import numpy as np
import os
import xarray as xr
import netCDF4 as nc
from time import strftime
from datetime import datetime
from scipy.spatial.distance import cdist
from scipy.optimize import minimize
import matplotlib.pyplot as plt
#========== IMPORT INPUT AND FUNCTIONS FROM MODULES ===================================================================
import pygem_input as input
import pygemfxns_modelsetup as modelsetup
import pygemfxns_climate as climate

#%% Write csv file from model results
# Create csv such that not importing the air temperature each time (takes 90 seconds for 13,119 glaciers)
#output_csvfullfilename = input.main_directory + '/../Output/ERAInterim_elev_15_SouthAsiaEast.csv'
#climate.createcsv_GCMvarnearestneighbor(input.gcm_prec_filename, input.gcm_prec_varname, dates_table, main_glac_rgi, 
#                                        output_csvfullfilename)
#np.savetxt(output_csvfullfilename, main_glac_gcmelev, delimiter=",") 


#%% Temperature bias correction between GCM and reference climate datasets
# Function input
option_bias_adjustment = 1
gcm_endyear = 2100
output_filepath = input.main_directory + '/../Climate_data/cmip5/bias_adjusted_1995_2100/'
output_filename_temp = 'tas_biasadj_1995_2100_tas_mon_MPI-ESM-LR_rcp26_r1i1p1_native.csv'
output_filename_prec = 'pr_biasadj_1995_2100_pr_mon_MPI-ESM-LR_rcp26_r1i1p1_native.csv'
output_filename_elev = 'elev_MPI-ESM-LR_rcp26_r1i1p1_native.csv'
output_filename_lr = 'lr_1995_2100_mon.csv'

# Filepath to GCM variable files
gcm_filepath_var = input.main_directory + '/../Climate_data/cmip5/rcp26_r1i1p1_monNG/'
# Filepath to GCM fixed variable files
gcm_filepath_fx = input.main_directory + '/../Climate_data/cmip5/rcp26_r0i0p0_fx/'
# Temperature filename and variable name
gcm_temp_filename = 'tas_mon_MPI-ESM-LR_rcp26_r1i1p1_native.nc'
gcm_temp_varname = 'tas'
# Precipitation filename and variable name
gcm_prec_filename = 'pr_mon_MPI-ESM-LR_rcp26_r1i1p1_native.nc'
gcm_prec_varname = 'pr'
# Elevation filename and variable name
gcm_elev_filename = 'orog_fx_MPI-ESM-LR_rcp26_r0i0p0.nc'
gcm_elev_varname = 'orog'
#modelparams_filename = 'calparams_R15_20180403_nearest.csv'

gcm_startyear=input.startyear
gcm_spinupyears=input.spinupyears

A = os.path.splitext(output_filename_temp)[0]

def gcm_bias_corrections(option_bias_adjustment, gcm_endyear, output_filepath,
                         gcm_startyear=input.startyear, 
                         gcm_spinupyears=input.spinupyears,
                         filepath_ref=input.filepath_ref, 
                         filename_ref_temp=input.gcmtemp_filedict[input.rgi_regionsO1[0]], 
                         filename_ref_prec=input.gcmprec_filedict[input.rgi_regionsO1[0]],
                         filename_ref_elev=input.gcmelev_filedict[input.rgi_regionsO1[0]], 
                         filename_ref_lr=input.gcmlapserate_filedict[input.rgi_regionsO1[0]], 
                         gcm_filepath_var=input.gcm_filepath_var,
                         gcm_filepath_fx=input.gcm_filepath_fx,
                         gcm_temp_filename=input.gcm_temp_filename, 
                         gcm_temp_varname=input.gcm_temp_varname,
                         gcm_prec_filename=input.gcm_prec_filename,
                         gcm_prec_varname=input.gcm_prec_varname, 
                         gcm_elev_filename=input.gcm_elev_filename,
                         gcm_elev_varname=input.gcm_elev_varname,
                         gcm_lat_varname=input.gcm_lat_varname,
                         gcm_lon_varname=input.gcm_lon_varname,
                         gcm_time_varname=input.gcm_time_varname,
                         filepath_modelparams=input.modelparams_filepath,
                         filename_modelparams=input.modelparams_filename):
    """
    Temperature bias corrections for future GCM projections given a calibrated reference time period
    Adjustment Options:
      Option 1 (default) - adjust the mean tempearture such that the cumulative positive degree days [degC*day] is equal
                 (cumulative positive degree days [degC*day] are exact)
      Option 2 - adjust so the mean temperature is the same for both datasets
                 (cumulative positive degree days [degC*day] can be significantly different)
      Option 3 - adjust the mean monthly temperature to be the same for both datasets
                 (cumulative positive degree days [degC*day] is closer than Option 1)
      Option 4 - adjust the mean monthly temperature and incorporate interannual variability [Huss and Hock, 2015]
                 (cumulative positive degree days [degC*day] is closer than Options 1 & 2)
      
    """
    
    # Select glaciers that adjustment is being performed on
    main_glac_rgi = modelsetup.selectglaciersrgitable()
    # Select dates including future projections
    dates_table, start_date, end_date = modelsetup.datesmodelrun(endyear=gcm_endyear)
    # Load reference data
    # Import air temperature, precipitation, lapse rates, and elevation from pre-processed csv files for a given region
    #  This saves time as opposed to running the nearest neighbor for the reference data as well
    ref_temp_all = np.genfromtxt(filepath_ref + filename_ref_temp, delimiter=',')
    ref_prec_all = np.genfromtxt(filepath_ref + filename_ref_prec, delimiter=',')
    ref_elev_all = np.genfromtxt(filepath_ref + filename_ref_elev, delimiter=',')
    ref_lr_all = np.genfromtxt(filepath_ref + filename_ref_lr, delimiter=',')
    modelparams_all = pd.read_csv(input.modelparams_filepath + input.modelparams_filename) 
    # Select the climate data for the glaciers included in the study
    if input.rgi_glac_number == 'all':
        ref_temp = ref_temp_all
        ref_prec = ref_prec_all
        ref_elev = ref_elev_all
        ref_lr = ref_lr_all
        modelparams = modelparams_all
    else:
        ref_temp = np.zeros((main_glac_rgi.shape[0], ref_temp_all.shape[1]))
        ref_prec = np.zeros((main_glac_rgi.shape[0], ref_temp_all.shape[1]))
        ref_elev = np.zeros((main_glac_rgi.shape[0]))
        ref_lr = np.zeros((main_glac_rgi.shape[0], ref_temp_all.shape[1]))
        modelparams = pd.DataFrame(np.zeros((main_glac_rgi.shape[0], modelparams_all.shape[1])), columns=input.modelparams_colnames)
        # Select climate data for each glacier using O1Index
        for glac in range(main_glac_rgi.shape[0]):
            ref_temp[glac,:] = ref_temp_all[main_glac_rgi.loc[glac,'O1Index'],:]
            ref_prec[glac,:] = ref_prec_all[main_glac_rgi.loc[glac,'O1Index'],:]
            ref_elev[glac] = ref_elev_all[main_glac_rgi.loc[glac,'O1Index']]
            ref_lr[glac,:] = ref_lr_all[main_glac_rgi.loc[glac,'O1Index'],:]
            modelparams.iloc[glac,:] = modelparams_all.iloc[main_glac_rgi.loc[glac,'O1Index'],:]
    # GCM data
    gcm_temp, gcm_dates = climate.importGCMvarnearestneighbor_xarray(
            gcm_temp_filename, gcm_temp_varname, main_glac_rgi, dates_table, start_date, end_date, 
            filepath=gcm_filepath_var, gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)
    gcm_prec, gcm_dates = climate.importGCMvarnearestneighbor_xarray(
            gcm_prec_filename, gcm_prec_varname, main_glac_rgi, dates_table, start_date, end_date, 
            filepath=gcm_filepath_var, gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)
    gcm_elev = climate.importGCMfxnearestneighbor_xarray(
            gcm_elev_filename, gcm_elev_varname, main_glac_rgi, filepath=gcm_filepath_fx, 
            gcm_lon_varname=gcm_lon_varname, gcm_lat_varname=gcm_lat_varname)
    # GCM subset to agree with reference time period to calculate bias corrections
    gcm_temp_subset = gcm_temp[:,0:ref_temp.shape[1]]
    gcm_prec_subset = gcm_prec[:,0:ref_temp.shape[1]]
    # Perform bias corrections
    if option_bias_adjustment == 1:
        # Adjust reference temperature to same elevation as GCM using the lapse rate
        ref_temp_adjusted = ref_temp + ref_lr*(gcm_elev - ref_elev)[:,np.newaxis]
        # Remove negative values for positive degree day calculation
        ref_temp_adjusted_pos = ref_temp_adjusted.copy()
        ref_temp_adjusted_pos[ref_temp_adjusted < 0] = 0
        # Select days per month
        daysinmonth = dates_table['daysinmonth'].values[0:ref_temp.shape[1]]
        # Cumulative positive degree days [degC*day] for reference period
        ref_PDD = (ref_temp_adjusted_pos * daysinmonth).sum(1)
        # Optimize bias adjustment such that PDD are equal
        bias_adj = np.zeros(ref_temp.shape[0])
        for glac in range(ref_temp.shape[0]):
            ref_PDD_glac = ref_PDD[glac]
            gcm_temp_glac = gcm_temp_subset[glac,:]
            def objective(bias_adj_glac):
                gcm_temp_glac_adj = gcm_temp_glac + bias_adj_glac
                gcm_temp_glac_adj[gcm_temp_glac_adj < 0] = 0
                gcm_PDD_glac = (gcm_temp_glac_adj * daysinmonth).sum()
                return abs(ref_PDD_glac - gcm_PDD_glac)
            # - initial guess
            bias_adj_init = 0      
            # - run optimization
            bias_adj_opt = minimize(objective, bias_adj_init, method='SLSQP', tol=1e-5)
            bias_adj[glac] = bias_adj_opt.x
        gcm_temp_bias_adj = gcm_temp + bias_adj[:,np.newaxis]
    elif option_bias_adjustment == 2:
        # Adjust reference temperature to same elevation as GCM using the lapse rate
        ref_temp_adjusted = ref_temp + ref_lr*(gcm_elev - ref_elev)[:,np.newaxis]
        # Reference - GCM difference
        difference_temp_all_mean = (ref_temp_adjusted - gcm_temp_subset).mean(axis=1)
        # Bias adjusted temperature accounting for mean of entire time period
        gcm_temp_bias_adj = gcm_temp + difference_temp_all_mean[:,np.newaxis]
    elif option_bias_adjustment == 3:
        # Adjust reference temperature to same elevation as GCM using the lapse rate
        ref_temp_adjusted = ref_temp + ref_lr*(gcm_elev - ref_elev)[:,np.newaxis]
        # Calculate monthly mean temperature
        ref_temp_monthly_avg = (ref_temp_adjusted.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .mean(1).reshape(12,-1).transpose())
        gcm_temp_monthly_avg = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .mean(1).reshape(12,-1).transpose())
        difference_temp_monthly_avg = ref_temp_monthly_avg - gcm_temp_monthly_avg
        # Bias adjusted temperature accounting for monthly mean
        gcm_temp_bias_adj = gcm_temp + np.tile(difference_temp_monthly_avg, int(gcm_temp.shape[1]/12))
    elif option_bias_adjustment == 4:
        # Adjust reference temperature to same elevation as GCM using the lapse rate
        ref_temp_adjusted = ref_temp + ref_lr*(gcm_elev - ref_elev)[:,np.newaxis]
        # Calculate monthly mean temperature
        ref_temp_monthly_avg = (ref_temp_adjusted.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .mean(1).reshape(12,-1).transpose())
        gcm_temp_monthly_avg = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .mean(1).reshape(12,-1).transpose())
        difference_temp_monthly_avg = ref_temp_monthly_avg - gcm_temp_monthly_avg
        # Monthly temperature bias adjusted according to monthly average
        t_mt = gcm_temp + np.tile(difference_temp_monthly_avg, int(gcm_temp.shape[1]/12))
        # Mean monthly temperature bias adjusted according to monthly average
        t_m25avg = np.tile(gcm_temp_monthly_avg + difference_temp_monthly_avg, int(gcm_temp.shape[1]/12))
        # Calculate monthly standard deviation of temperature
        ref_temp_monthly_std = (ref_temp_adjusted.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .std(1).reshape(12,-1).transpose())
        gcm_temp_monthly_std = (gcm_temp_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                                .std(1).reshape(12,-1).transpose())
        variability_monthly_std = ref_temp_monthly_std / gcm_temp_monthly_std
        # Bias adjusted temperature accounting for monthly mean and variability
        gcm_temp_bias_adj = t_m25avg + (t_mt - t_m25avg) * np.tile(variability_monthly_std, int(gcm_temp.shape[1]/12))
    # BIAS ADJUSTED PRECIPITATION
    # Adjust reference precipitation to same elevation as GCM using the precipitation gradient
    ref_prec_adjusted = ref_prec * (1 + modelparams['precgrad'].values[:,np.newaxis] * (gcm_elev - ref_elev)[:,np.newaxis])
    # Calculate monthly mean precipitation
    ref_prec_monthly_avg = (ref_prec_adjusted.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                            .mean(1).reshape(12,-1).transpose())
    gcm_prec_monthly_avg = (gcm_prec_subset.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12))
                            .mean(1).reshape(12,-1).transpose())
    difference_prec_monthly_avg = ref_prec_monthly_avg / gcm_prec_monthly_avg
    # Bias adjusted precipitation accounting for differences in monthly mean
    gcm_prec_bias_adj = gcm_prec * np.tile(difference_prec_monthly_avg, int(gcm_temp.shape[1]/12))
    # LAPSE RATE - MONTHLY MEAN
    ref_lr_monthly_avg = (ref_lr.reshape(-1,12).transpose().reshape(-1,int(ref_temp.shape[1]/12)).mean(1).reshape(12,-1)
                          .transpose())
    gcm_lr = np.tile(ref_lr_monthly_avg, int(gcm_temp.shape[1]/12))
    # OUTPUT FILES TO CSV
    output_prefix = 'biasadj_' + str(gcm_startyear - gcm_spinupyears) + '_' + str(gcm_endyear) + '_'
    output_filename_temp = output_prefix + os.path.splitext(gcm_temp_filename)[0] + '.csv'
    output_filename_prec = output_prefix + os.path.splitext(gcm_prec_filename)[0] + '.csv'
    output_filename_elev = output_prefix + os.path.splitext(gcm_elev_filename)[0] + '.csv'
    output_filename_lr =   output_prefix + 'lr_mon.csv' 
    np.savetxt(output_filepath + output_filename_temp, gcm_temp_bias_adj, delimiter=",") 
    np.savetxt(output_filepath + output_filename_prec, gcm_prec_bias_adj, delimiter=",") 
    np.savetxt(output_filepath + output_filename_elev, gcm_elev, delimiter=",") 
    np.savetxt(output_filepath + output_filename_lr, gcm_lr, delimiter=",") 
    return gcm_temp_bias_adj, gcm_prec_bias_adj, gcm_elev, gcm_lr, modelparams

gcm_temp_bias_adj, gcm_prec_bias_adj, gcm_elev, gcm_lr, modelparams = gcm_bias_corrections(
        option_bias_adjustment, gcm_endyear, output_filepath)


#%% Create netcdf file of lapse rates from temperature pressure level data
def lapserates_createnetcdf(gcm_filepath, gcm_filename_prefix, tempname, levelname, latname, lonname, elev_idx_max, 
                            elev_idx_min, startyear, endyear, output_filepath, output_filename_prefix):
    """
    Create a netcdf with the lapse rate for every latitude/longitude for each month.  The lapse rates are computed based
    on the slope of a linear line of best fit for the temperature pressure level data.
    Note: prior to running this function, you must explore the temperature pressure level data to determine the
          elevation range indices for a given region, variable names, etc.
    """
    fullfilename = gcm_filepath + gcm_filename_prefix + str(startyear) + '.nc'
    data = xr.open_dataset(fullfilename)    
    # Extract the pressure levels [Pa]
    if data[levelname].attrs['units'] == 'millibars':
        # Convert pressure levels from millibars to Pa
        levels = data[levelname].values * 100
    # Compute the elevation [m a.s.l] of the pressure levels using the barometric pressure formula (pressure in Pa)
    elev = -input.R_gas*input.temp_std/(input.gravity*input.molarmass_air)*np.log(levels/input.pressure_std)
    # Netcdf file for lapse rates ('w' will overwrite existing file)
    output_fullfilename = output_filepath + output_filename_prefix + '_' + str(startyear) + '_' + str(endyear) + '.nc'
    netcdf_output = nc.Dataset(output_fullfilename, 'w', format='NETCDF4')
    # Global attributes
    netcdf_output.description = 'Lapse rates from ERA Interim pressure level data that span the regions elevation range'
    netcdf_output.history = 'Created ' + str(strftime("%Y-%m-%d %H:%M:%S"))
    netcdf_output.source = 'ERA Interim reanalysis data downloaded February 2018'
    # Dimensions
    latitude = netcdf_output.createDimension('latitude', data['latitude'].values.shape[0])
    longitude = netcdf_output.createDimension('longitude', data['longitude'].values.shape[0])
    time = netcdf_output.createDimension('time', None)
    # Create dates in proper format for time dimension
    startdate = str(startyear) + '-01-01'
    enddate = str(endyear) + '-12-31'
    startdate = datetime(*[int(item) for item in startdate.split('-')])
    enddate = datetime(*[int(item) for item in enddate.split('-')])
    startdate = startdate.strftime('%Y-%m')
    enddate = enddate.strftime('%Y-%m')
    dates = pd.DataFrame({'date' : pd.date_range(startdate, enddate, freq='MS')})
    dates = dates['date'].astype(datetime)
    # Variables associated with dimensions 
    latitude = netcdf_output.createVariable('latitude', np.float32, ('latitude',))
    latitude.long_name = 'latitude'
    latitude.units = 'degrees_north'
    latitude[:] = data['latitude'].values
    longitude = netcdf_output.createVariable('longitude', np.float32, ('longitude',))
    longitude.long_name = 'longitude'
    longitude.units = 'degrees_east'
    longitude[:] = data['longitude'].values
    time = netcdf_output.createVariable('time', np.float64, ('time',))
    time.long_name = "time"
    time.units = "hours since 1900-01-01 00:00:00"
    time.calendar = "gregorian"
    time[:] = nc.date2num(dates, units=time.units, calendar=time.calendar)
    lapserate = netcdf_output.createVariable('lapserate', np.float64, ('time', 'latitude', 'longitude'))
    lapserate.long_name = "lapse rate"
    lapserate.units = "degC m-1"
    # Set count to keep track of time position
    count = 0
    for year in range(startyear,endyear+1):
        print(year)
        fullfilename_year = gcm_filepath + gcm_filename_prefix + str(year) + '.nc'
        data_year = xr.open_dataset(fullfilename_year)
        count = count + 1
        for lat in range(0,latitude[:].shape[0]):
            for lon in range(0,longitude[:].shape[0]):
                data_subset = data_year[tempname].isel(level=range(elev_idx_max,elev_idx_min+1), 
                                                       latitude=lat, longitude=lon).values
                lapserate_subset = (((elev[elev_idx_max:elev_idx_min+1] * data_subset).mean(axis=1) - 
                                     elev[elev_idx_max:elev_idx_min+1].mean() * data_subset.mean(axis=1)) / 
                                    ((elev[elev_idx_max:elev_idx_min+1]**2).mean() - 
                                     (elev[elev_idx_max:elev_idx_min+1].mean())**2))
                lapserate[12*(count-1):12*count,lat,lon] = lapserate_subset
                # Takes roughly 4 minutes per year to compute the lapse rate for each lat/lon combo in HMA
    netcdf_output.close()
        
## Application of the lapserate_createnetcdf function
#gcm_filepath = os.getcwd() + '/../Climate_data/ERA_Interim/HMA_temp_pressurelevel_data/'
#gcm_filename_prefix = 'HMA_EraInterim_temp_pressurelevels_'
#tempname = 't'
#levelname = 'level'
#latname = 'latitude'
#lonname = 'longitude'
#elev_idx_max = 1
#elev_idx_min = 10
#startyear = 1979
#endyear = 2017
#output_filepath = '../Output/'
#output_filename_prefix = 'HMA_Regions13_14_15_ERAInterim_lapserates'
#lapserates_createnetcdf(gcm_filepath, gcm_filename_prefix, tempname, levelname, latname, lonname, elev_idx_max, 
#                        elev_idx_min, startyear, endyear, output_filepath, output_filename_prefix)  


#%% Mass redistribution parameters based on geodetic mass balances
#mb_filepath = os.getcwd() + '/../../HiMAT/DEMs/mb_bins_sample_20180323/'
#mb_filename = '15.10070_CN5O193B0118EastRongbukGlacier_mb_bins.csv'
#
#data = pd.read_csv(mb_filepath + mb_filename)
#elev = data['# bin_center_elev_m']
#elev_norm = (elev.max() - elev) / (elev.max() - elev.min())
#dhdt = data[' dhdt_bin_mean_ma']
#dhdt_norm = (dhdt.max() - dhdt) / (dhdt.max() - dhdt.min())
#
##plt.scatter(elev_norm, dhdt_norm, cmap='jet_r')
###  plotting x, y, size [s=__], color bar [c=__]
###  set the range of the color bar
##plt.colorbar(fraction=0.02, pad=0.04)
###  fraction resizes the colorbar, pad is the space between the plot and colorbar
##plt.show()
#
#fig, ax = plt.subplots(1,1, figsize=(5,5))  
#markers = ['o','v','^']
#labels = ['15.100070', '0.0003', '0.0005']
### define the colormap
##cmap = plt.cm.jet_r
### extract all colors from the .jet map
##cmaplist = [cmap(i) for i in range(cmap.N)]
### create the new map
##cmap = cmap.from_list('Custom cmap', cmaplist, cmap.N)
### define the bins and normalize
##stepmin = 0
##stepmax = 1
##stepsize = 0.2
##bounds = np.arange(stepmin, stepmax, stepsize)
##norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
#
## make the scatter
#scat = ax.scatter(elev_norm, dhdt_norm, marker=markers[0], label=labels[0])
## create the colorbar
##cb = plt.colorbar(scat, spacing='proportional', ticks=bounds)
##cb = plt.colorbar()
##tick_loc = bounds + stepsize/2
##cb.set_ticks(tick_loc)
##cb.set_ticklabels((bounds + stepsize/2).astype(int))
##cb.set_label('Tempchange [degC]')
##ax.set_title('TITLE')
#plt.xlabel('Normalized elevation range')
#plt.xlim((0, 1))
##plt.xticks(np.arange(0,1.1,0.2))
#plt.ylabel('Normalized ice thickness change')
#plt.ylim((1,0))
##plt.legend(loc=2)
#plt.show()
##fig.savefig(input.main_directory + '/../output/' + main_glac_rgi.loc[glac,'RGIID'] + '_gridsearch.png')


#%% NEAREST NEIGHBOR CALIBRATION PARAMETERS
## Load csv
#ds = pd.read_csv(input.main_directory + '/../Output/calibration_R15_20180403_Opt02solutionspaceexpanding.csv', 
#                 index_col='GlacNo')
## Select data of interest
#data = ds[['CenLon', 'CenLat', 'lrgcm', 'lrglac', 'precfactor', 'precgrad', 'ddfsnow', 'ddfice', 'tempsnow', 'tempchange']].copy()
## Drop nan data to retain only glaciers with calibrated parameters
#data_cal = data.dropna()
#A = data_cal.mean(0)
## Select latitude and longitude of calibrated parameters for distance estimate
#data_cal_lonlat = data_cal.iloc[:,0:2].values
## Loop through each glacier and select the parameters based on the nearest neighbor
#for glac in range(data.shape[0]):
#    # Avoid applying this to any glaciers that already were optimized
#    if data.iloc[glac, :].isnull().values.any() == True:
#        # Select the latitude and longitude of the glacier's center
#        glac_lonlat = data.iloc[glac,0:2].values
#        # Set point to be compatible with cdist function (from scipy)
#        pt = [[glac_lonlat[0],glac_lonlat[1]]]
#        # scipy function to calculate distance
#        distances = cdist(pt, data_cal_lonlat)
#        # Find minimum index (could be more than one)
#        idx_min = np.where(distances == distances.min())[1]
#        # Set new parameters
#        data.iloc[glac,2:] = data_cal.iloc[idx_min,2:].values.mean(0)
#        #  use mean in case multiple points are equidistant from the glacier
## Remove latitude and longitude to create csv file
#parameters_export = data.iloc[:,2:]
## Export csv file
#parameters_export.to_csv(input.main_directory + '/../Calibration_datasets/calparams_R15_20180403_nearest.csv', 
#                         index=False)


#%% Connect the WGMS point mass balance datasets with the RGIIds and relevant elevation bands
## Bounding box
#lat_bndN = 46
#lat_bndS = 26
#lon_bndW = 65
#lon_bndE = 105
#
## Load RGI lookup table 
#rgilookup_filename = input.main_directory + '/../RGI/rgi60/00_rgi60_links/00_rgi60_links.csv'
#rgilookup = pd.read_csv(rgilookup_filename, skiprows=2)
#rgidict = dict(zip(rgilookup['FoGId'], rgilookup['RGIId']))
## Load WGMS lookup table
#wgmslookup_filename = (input.main_directory + 
#                       '/../Calibration_datasets\DOI-WGMS-FoG-2017-10\WGMS-FoG-2017-10-AA-GLACIER-ID-LUT.csv')
#wgmslookup = pd.read_csv(wgmslookup_filename, encoding='latin1')
#wgmsdict = dict(zip(wgmslookup['WGMS_ID'], wgmslookup['RGI_ID']))
## Manual lookup table
#manualdict = {10402: 'RGI60-13.10093',
#              10401: 'RGI60-15.03734',
#              6846: 'RGI60-15.12707'}
## WGMS POINT MASS BALANCE DATA
## Load WGMS point mass balance data
#wgms_massbal_pt_filename = (input.main_directory + 
#                            '/../Calibration_datasets\DOI-WGMS-FoG-2017-10/WGMS-FoG-2017-10-EEE-MASS-BALANCE-POINT.csv')
#wgms_massbal_pt = pd.read_csv(wgms_massbal_pt_filename, encoding='latin1')
#
## Select values based on the bounding box
#wgms_massbal_pt = wgms_massbal_pt[(wgms_massbal_pt['POINT_LAT'] <= lat_bndN) & 
#                                  (wgms_massbal_pt['POINT_LAT'] >= lat_bndS) & 
#                                  (wgms_massbal_pt['POINT_LON'] <= lon_bndE) &
#                                  (wgms_massbal_pt['POINT_LON'] >= lon_bndW)]
## Remove values without an elevation
#wgms_massbal_pt = wgms_massbal_pt[wgms_massbal_pt['POINT_ELEVATION'].isnull() == False]
## Select values within yearly range
#wgms_massbal_pt = wgms_massbal_pt[(wgms_massbal_pt['YEAR'] >= input.startyear) & 
#                                  (wgms_massbal_pt['YEAR'] <= input.endyear)]
## Find the RGIId for each WGMS glacier
#wgms_massbal_pt_Ids = pd.DataFrame()
#wgms_massbal_pt_Ids['WGMS_ID'] = wgms_massbal_pt['WGMS_ID'].value_counts().index.values
#wgms_massbal_pt_Ids['RGIId'] = np.nan
#wgms_massbal_pt_Ids['RGIId_wgms'] = wgms_massbal_pt_Ids['WGMS_ID'].map(wgmsdict)
#wgms_massbal_pt_Ids['RGIId_rgi'] = wgms_massbal_pt_Ids['WGMS_ID'].map(rgidict)
#wgms_massbal_pt_Ids['RGIId_manual'] = wgms_massbal_pt_Ids['WGMS_ID'].map(manualdict)
#
#for glac in range(wgms_massbal_pt_Ids.shape[0]):
#    if pd.isnull(wgms_massbal_pt_Ids.loc[glac,'RGIId_wgms']) == False:
#        wgms_massbal_pt_Ids.loc[glac,'RGIId'] = wgms_massbal_pt_Ids.loc[glac,'RGIId_wgms']
#    elif pd.isnull(wgms_massbal_pt_Ids.loc[glac,'RGIId_rgi']) == False:
#        wgms_massbal_pt_Ids.loc[glac,'RGIId'] = wgms_massbal_pt_Ids.loc[glac,'RGIId_rgi']
#    elif pd.isnull(wgms_massbal_pt_Ids.loc[glac,'RGIId_manual']) == False:
#        wgms_massbal_pt_Ids.loc[glac,'RGIId'] = wgms_massbal_pt_Ids.loc[glac,'RGIId_manual']
#
## WGMS GEODETIC MASS BALANCE DATA 
## Load WGMS geodetic mass balance data
#wgms_massbal_geo_filename = (input.main_directory + 
#                            '/../Calibration_datasets\DOI-WGMS-FoG-2017-10/WGMS-FoG-2017-10-EE-MASS-BALANCE.csv')
#wgms_massbal_geo = pd.read_csv(wgms_massbal_geo_filename, encoding='latin1')
## Load WGMS glacier table to look up lat/lon that goes with the glacier
#wgms_massbal_geo_lookup_filename = (input.main_directory + 
#                            '/../Calibration_datasets\DOI-WGMS-FoG-2017-10/WGMS-FoG-2017-10-A-GLACIER.csv')
#wgms_massbal_geo_lookup = pd.read_csv(wgms_massbal_geo_lookup_filename, encoding='latin1')
## Create WGMSID - lat/lon dictionaries
#wgms_latdict = dict(zip(wgms_massbal_geo_lookup['WGMS_ID'], wgms_massbal_geo_lookup['LATITUDE']))
#wgms_londict = dict(zip(wgms_massbal_geo_lookup['WGMS_ID'], wgms_massbal_geo_lookup['LONGITUDE']))
## Add latitude and longitude to wgms_massbal_measurements
#wgms_massbal_geo['LATITUDE'] = wgms_massbal_geo['WGMS_ID'].map(wgms_latdict)
#wgms_massbal_geo['LONGITUDE'] = wgms_massbal_geo['WGMS_ID'].map(wgms_londict)
## Select values based on the bounding box
#wgms_massbal_geo = wgms_massbal_geo[(wgms_massbal_geo['LATITUDE'] <= lat_bndN) & 
#                                    (wgms_massbal_geo['LATITUDE'] >= lat_bndS) & 
#                                    (wgms_massbal_geo['LONGITUDE'] <= lon_bndE) &
#                                    (wgms_massbal_geo['LONGITUDE'] >= lon_bndW)]
## Select only glacier-wide values (LOWER_BOUND / UPPER_BOUND = 9999)
#wgms_massbal_geo = wgms_massbal_geo[wgms_massbal_geo['LOWER_BOUND'] == 9999]
## Select values within yearly range
#wgms_massbal_geo = wgms_massbal_geo[(wgms_massbal_geo['YEAR'] >= input.startyear) & 
#                                    (wgms_massbal_geo['YEAR'] <= input.endyear)]
## Find the RGIId for each WGMS glacier
#wgms_massbal_geo_Ids = pd.DataFrame()
#wgms_massbal_geo_Ids['WGMS_ID'] = wgms_massbal_geo['WGMS_ID'].value_counts().index.values
#wgms_massbal_geo_Ids['RGIId'] = np.nan
#wgms_massbal_geo_Ids['RGIId_wgms'] = wgms_massbal_geo_Ids['WGMS_ID'].map(wgmsdict)
#wgms_massbal_geo_Ids['RGIId_rgi'] = wgms_massbal_geo_Ids['WGMS_ID'].map(rgidict)
#wgms_massbal_geo_Ids['RGIId_manual'] = wgms_massbal_geo_Ids['WGMS_ID'].map(manualdict)
## Consolidate dictionaries to one RGIID
#for glac in range(wgms_massbal_geo_Ids.shape[0]):
#    if pd.isnull(wgms_massbal_geo_Ids.loc[glac,'RGIId_wgms']) == False:
#        wgms_massbal_geo_Ids.loc[glac,'RGIId'] = wgms_massbal_geo_Ids.loc[glac,'RGIId_wgms']
#    elif pd.isnull(wgms_massbal_geo_Ids.loc[glac,'RGIId_rgi']) == False:
#        wgms_massbal_geo_Ids.loc[glac,'RGIId'] = wgms_massbal_geo_Ids.loc[glac,'RGIId_rgi']
#    elif pd.isnull(wgms_massbal_geo_Ids.loc[glac,'RGIId_manual']) == False:
#        wgms_massbal_geo_Ids.loc[glac,'RGIId'] = wgms_massbal_geo_Ids.loc[glac,'RGIId_manual']
## Create dictionary from WGMS_ID to RGIID
#wgms_massbal_geo_dict = dict(zip(wgms_massbal_geo_Ids['WGMS_ID'], wgms_massbal_geo_Ids['RGIId']))
## Add RGIID to geodetic measurements
#wgms_massbal_geo['RGIId'] = wgms_massbal_geo['WGMS_ID'].map(wgms_massbal_geo_dict)
## Remove values without a RGIId
#wgms_massbal_geo = wgms_massbal_geo[wgms_massbal_geo['RGIId'].isnull() == False]

#%% Conslidate the WGMS data into a single csv file for a given WGMS-defined region  
### Inputs for mass balance glaciological method
###filepath = os.getcwd() + '/../WGMS/Asia_South_East_MB_glac_method/'
##filepath = os.getcwd() + '/../WGMS/Asia_South_West_MB_glac_method/'
##filename_prefix = 'FoG_MB_'
##skiprows_value = 13
#
## Inputs for mass balance (glacier thickness change) from geodetic approach
##filepath = os.getcwd() + '/../WGMS/Asia_South_East_Thickness_change_geodetic/'
#filepath = os.getcwd() + '/../WGMS/Asia_South_West_Thickness_change_geodetic/'
#filename_prefix = 'FoG_TC_'
#skiprows_value = 16
#    
#data = None
#for filename in os.listdir(filepath):
#    print(filename)
#    try:
#        # try reading csv with default encoding
#        data_subset = pd.read_csv(filepath + filename, delimiter = ';', skiprows=skiprows_value, quotechar='"')
#    except:
#        # except try reading with latin1, which handles accents
#        data_subset = pd.read_csv(filepath + filename, delimiter = ';', skiprows=skiprows_value, quotechar='"', encoding='latin1')
#        
#    # Append data to create one dataframe
#    if data is None:
#        data = data_subset
#    else:
#        data = data.append(data_subset)
## Sort data according to ID and survey year
#data = data.sort_values(by=['WGMS_ID', 'SURVEY_YEAR'])     
    
    