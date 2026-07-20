from dmi_frie_data.http import DMIHTTPClient
from dmi_frie_data import DMIClient, RadarQuery
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np


def ewlma(data, window, alpha=None):
    """
    Finite-window (limited) exponentially weighted moving average.

    Parameters
    ----------
    data : ndarray
        Input array. EWMA is computed along the last axis.
    window : int
        Number of most recent observations to include.
    alpha : float, optional
        Exponential decay parameter. Defaults to 2/(window+1).

    Returns
    -------
    out : ndarray
        Same shape as data.
    """
    data = np.asarray(data, dtype=np.float64)
    if alpha is None:
        alpha = 2.0 / (window + 1.0)
    weights = alpha * (1 - alpha) ** np.arange(window - 1, -1, -1)
    out = np.full_like(data, np.nan)
    T = data.shape[-1]
    for t in range(T):
        start = max(0, t - window + 1)
        x = data[..., start:t+1]
        w = weights[-x.shape[-1]:]
        mask = np.isfinite(x)
        num = np.sum(np.where(mask, x * w, 0.0), axis=-1)
        den = np.sum(np.where(mask, w, 0.0), axis=-1)
        np.divide(num, den, out=out[..., t], where=den > 0)
    return out

client = DMIClient()
items = client.radar.query(RadarQuery(collection='composite', period='3H', sortorder='datetime,DESC'))
items.features = items.features[::-1]

timeseries = []

for feature in items.features:
    feature = feature
    array = feature.as_array(http_client=DMIHTTPClient()).astype(float)
    array[array==255] = np.nan
    timeseries.append(array)

timeseries = np.transpose(np.array(timeseries))

ts_ma = ewlma(timeseries, 4)

timeseries = np.transpose(ts_ma)

cropped = []

for field in timeseries[1:]:
    rows = np.any(np.isfinite(field), axis=1)
    cols = np.any(np.isfinite(field), axis=0)
    cropped.append(field[rows][:, cols])

timeseries = np.array(cropped)
    
# timeseries[timeseries <= 1] = np.nan

##### Cartopy plot
import cartopy.crs as ccrs
import cartopy.feature as cfeature

bbox = items.features[0].bbox
lon_min, lon_max, lat_min, lat_max = [4.65, 18.6000, 52.9402, 59.615]
field = timeseries[0] 
lons = np.linspace(lon_min, lon_max, field.shape[1])
lats = np.linspace(lat_min, lat_max, field.shape[0])
Lon, Lat = np.meshgrid(lons, lats)

proj = ccrs.LambertConformal(
    central_longitude=(lon_min + lon_max) / 2,
    central_latitude=(lat_min + lat_max) / 2,
    standard_parallels=(54, 58),
)
fig = plt.figure(figsize=(15, 10))
ax = fig.add_subplot(1, 1, 1, projection=proj)
ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

pcm = ax.pcolormesh(
    lons,
    lats,
    np.flip(field, 0),
    transform=ccrs.PlateCarree(),
    shading="auto",
    cmap="viridis",
)
title = ax.set_title(f"Radar Data: {items.features[0].properties['datetime']}")

ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.8)
ax.add_feature(cfeature.LAND, edgecolor='black', facecolor='lightgray')
ax.add_feature(cfeature.OCEAN, facecolor='lightblue')

gl = ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False, alpha=0.5, linestyle='--')
gl.top_labels = False
gl.right_labels = False


def update(frame):
    current_frame = timeseries[frame]
    pcm.set_array(np.flip(current_frame, 0))
    title.set_text(f"Radar Data: {items.features[frame].properties['datetime']}")
    return pcm, title

anim = FuncAnimation(fig, update, frames=len(timeseries), interval=500, blit=True)

with open("yourhtmlfile.html", "w") as file:
    file.write(anim.to_html5_video())
##### Geojson/geopandas plot
gdfs = []

for t in range(len(timeseries)):
    feature = items.features[t]
    geojson = feature.to_geojson(array=timeseries[t])
    gdfs.append(gpd.GeoDataFrame.from_features(geojson['features']))
    print(t)

gdf = pd.concat(gdfs)

gdf['datetime'] = pd.to_datetime(gdf['datetime'])
timestamps = gdf['datetime'].unique()

fig, ax = plt.subplots(figsize=(8, 6))
vmin = gdf['value'].min()
vmax = gdf['value'].max()

ax.clear() 
ax.axis('off')
current_ts = timestamps[frame]
sub_gdf = gdf[gdf['datetime'] == current_ts]
sub_gdf.plot(
    column='value',
    ax=ax,
    cmap='viridis',
    vmin=vmin,
    vmax=vmax,
    legend=True if frame == 0 else False 
)

formatted_time = pd.to_datetime(current_ts).strftime('%Y-%m-%d %H:%M')
ax.set_title(f"Tidsserie: {formatted_time}", fontsize=14)


def update(frame):
    ax.clear() 
    ax.axis('off')
    current_ts = timestamps[frame]
    sub_gdf = gdf[gdf['datetime'] == current_ts]
    sub_gdf.plot(
        column='value',
        ax=ax,
        cmap='viridis',
        vmin=vmin,
        vmax=vmax,
        legend=True if frame == 0 else False 
    )
    
    formatted_time = pd.to_datetime(current_ts).strftime('%Y-%m-%d %H:%M')
    ax.set_title(f"Tidsserie: {formatted_time}", fontsize=14)

anim = FuncAnimation(fig, update, frames=len(timestamps), interval=500, repeat=True)
plt.close() 


with open("yourhtmlfile.html", "w") as file:
    file.write(anim.to_html5_video())