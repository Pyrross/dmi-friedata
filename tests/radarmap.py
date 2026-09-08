import h5py
import numpy as np
import numpy.ma as ma
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import Normalize
import os
import sys

def parse_projdef(projdef_str):
    """Parse a proj4 string into a dictionary."""
    parts = [p for p in projdef_str.strip().split() if p]
    proj_params = {}
    for part in parts:
        if '=' in part:
            key, value = part.lstrip('+').split('=')
            try:
                value = float(value)
            except ValueError:
                pass
            proj_params[key] = value
        else:
            proj_params[part.lstrip('+')] = True  # e.g. +no_defs
    return proj_params

def get_cartopy_crs_from_projdef(projdef_str):
    """Map proj4 string to Cartopy CRS."""
    params = parse_projdef(projdef_str)
    proj_name = params.get('proj')
    print(params)
    if proj_name == 'laea':
        crs = ccrs.LambertAzimuthalEqualArea(
            central_longitude=params.get('lon_0', 0),
            central_latitude=params.get('lat_0', 0),
            false_easting=params.get('x_0', 0),
            false_northing=params.get('y_0', 0)
        )
        print('projection', crs)
        return crs
    elif proj_name == 'stere':
        crs = ccrs.Stereographic(
            central_longitude=params.get('lon_0', 0),
            central_latitude=params.get('lat_0', 0),
            false_easting=params.get('x_0', 0),
            false_northing=params.get('y_0', 0),
            true_scale_latitude=params.get('lat_ts', 0),
        )
        print('projection', crs)
        return crs
    else:
        raise NotImplementedError(f'Projection {proj_name} not implemented yet.')

# https://opendataapi.dmi.dk/v1/radardata/download/dk.com.202609081245.500_max.h5
with h5py.File("dk.com.202609081240.500_max.h5", "r") as f:
    where_grp = f["where"].attrs if "where" in f else f.attrs
    LL_lon = float(where_grp["LL_lon"][0])
    LL_lat = float(where_grp["LL_lat"][0])
    UL_lon = float(where_grp["UL_lon"][0])
    UL_lat = float(where_grp["UL_lat"][0])
    UR_lon = float(where_grp["UR_lon"][0])
    UR_lat = float(where_grp["UR_lat"][0])
    LR_lon = float(where_grp["LR_lon"][0])
    LR_lat = float(where_grp["LR_lat"][0])
    print("Bounding Corners:")
    print(f"Lower-Left  (LL): ({LL_lon:.6f}, {LL_lat:.6f})")
    print(f"Upper-Left  (UL): ({UL_lon:.6f}, {UL_lat:.6f})")
    print(f"Upper-Right (UR): ({UR_lon:.6f}, {UR_lat:.6f})")
    print(f"Lower-Right (LR): ({LR_lon:.6f}, {LR_lat:.6f})")
    # Output:
    # Bounding Corners:
    # Lower-Left  (LL): (4.379083, 52.294272)
    # Upper-Left  (UL): (3.000000, 60.000000)
    # Upper-Right (UR): (20.735140, 59.827708)
    # Lower-Right (LR): (18.893281, 52.294272)
    LR_lat = 52.159161  # Fixing coordinate bug
    data = f['/dataset1/data1/data'][:]
    what_attrs = f['what'].attrs
    quantity = 'DBZH'
    nodata_value = what_attrs['nodata']
    undetect_value = what_attrs['undetect']
    gain = what_attrs['gain']
    offset = what_attrs['offset']
    # Apply gain and offset to transform the data into physical quantities
    data_transformed = data * gain + offset
    # Masked nodata and undetect values
    data_transformed = ma.masked_equal(data_transformed, nodata_value)
    data_transformed = ma.masked_equal(data_transformed, undetect_value)
    # Make computations on data, e.g. mean reflectivity
    data_mean = np.mean(data_transformed)
    # Get projection info
    proj_attrs = f['/where'].attrs
    xscale = proj_attrs['xscale']
    yscale = proj_attrs['yscale']
    # Get projection definition string
    projdef = f['/where'].attrs['projdef'].decode()
    startdate = f['/what'].attrs['date'].decode()
    starttime = f['/what'].attrs['time'].decode()

# Create CRS from projdef string
source_crs = get_cartopy_crs_from_projdef(projdef)

# Make map
fig = plt.figure(figsize=(10, 10))
ax = plt.axes(projection=source_crs)

cmap = plt.cm.viridis

# Set colors for undetect (white) and nodata (light gray)
cmap.set_under('white')  # For undetect values (set this to white)
cmap.set_bad('lightgray')  # For nodata values (set this to light gray)

vmin = -31.5
vmax = 96.0
norm = Normalize(vmin=0, vmax=vmax)

# Display the radar image with colormap and normalization
data_display = data_transformed.copy()

# Set values out of range (nodata) to nan and undetected values to
# small number (for display)
data_display[np.where(data == undetect_value)] = -8888000.0
data_display[np.where(data == nodata_value)] = np.nan

# Transform UL and LR geographic coordinates to map coordinates
transformer = source_crs.transform_points(ccrs.PlateCarree(),
                                           np.array([UL_lon, LR_lon]),
                                           np.array([UL_lat, LR_lat]))

print('Extent, geographic coordinates UL_lon, YL_lat', UL_lon, UL_lat)
print('Extent, geographic coordinates LR_lon, LR_lat', LR_lon, LR_lat)

UL_x, UL_y = transformer[0, 0], transformer[0, 1]
LR_x, LR_y = transformer[1, 0], transformer[1, 1]

print('Extent, map coordinates UL_x, YL_y', UL_x, UL_y)
print('Extent, map coordinates LR_x, LR_y', LR_x, LR_y)

ax.set_xlim(UL_x, LR_x)
ax.set_ylim(LR_y, UL_y)

# Display the image
img = ax.imshow(data_display, cmap=cmap, origin='upper',  # Change origin to 'upper' or 'lower' according to origo
                norm=norm, extent=(UL_x, LR_x, LR_y, UL_y))

# Add coastlines and country borders
ax.coastlines(resolution='10m', linewidth=0.5)
ax.add_feature(cfeature.BORDERS, linewidth=0.25)

# Add colorbar
cbar = plt.colorbar(img, ax=ax, label=f'{quantity}')

# Add map title
prodname = 'DMI radar composite reflectivity'
plt.title(f'{prodname} ({quantity})\nStart Date: {startdate} {starttime}\nMean {data_mean:0.1f} dBZ')

# Save map as PNG if not already saved
outfilename = 'out_radarmap_fr.png'
if not os.path.isfile(outfilename):
    plt.savefig(outfilename, dpi=150, bbox_inches='tight')
else:
    print(f'Outputfile already exists {outfilename} ... skipping')

# Show map
plt.show()
