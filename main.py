import time
from datetime import datetime, timedelta
import chardet
from pathlib import Path
from shutil import rmtree
from zipfile import ZipFile
from typing import Optional, List
import aiofiles
from pydantic import BaseModel
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
import uvicorn
import os, io, glob, uuid
import folium as folium
import pandas as pd
import geopandas, fiona
import matplotlib.pyplot as plt
from exif import Image as Img
import xlsxwriter
from starlette.responses import Response
import difflib


class GPSExifData:
    Image_name: str
    # GPS_make: str
    # GPS_model: str
    # GPS_time: str
    GPS_latitude: float
    GPS_longitude: float
    # GPS_direction: float

########map style######
# tiles=
# tiles="cartodbdark_matter",
# tiles="cartodbpositron",
# tiles='Stamen Toner',
# iles='Stamen Terrain',
# tiles = 'openstreetmap',

app = FastAPI()

###### Params #####
image_list = []
all_tag = []
Name = []
Time = []
Make = []
Model = []
Direction = []
Lat = []
Long = []
folder_name = "IN_FILES"
temp_path = os.getcwd() + "/" + folder_name
DEL_FOLDER = True

# print(f"new_path {temp_path}")
##### Pandas Data Frame #####
# df1 = pd.DataFrame()
# df2 = pd.DataFrame()

####TODO#####
# folder_name = "FILE_NAME"
# file_path = os.getcwd() + "/" + folder_name
#delete folder#
def delete_folder(temp_path):
    if DEL_FOLDER:
        rmtree(temp_path)
    else:
        pass


def read_image_name(folder_path):
    for filename in glob.glob(os.path.join(folder_path, '*.JPG')):
        with open(filename, mode='rb') as f:
            text = f.readlines()
            #image_list.clear()
            image_list.append(filename)
            print("get")
    return image_list


def dms_to_dd(gps_coords, gps_coords_ref):
    d, m, s = gps_coords
    dd = d + m / 60 + s / 3600
    if gps_coords_ref.upper() in ('S', 'W'):
        return -dd
    elif gps_coords_ref.upper() in ('N', 'E'):
        return dd
    else:
        raise RuntimeError('Incorrect gps_coords_ref {}'.format(gps_coords_ref))


def image_to_exif(images_list):
    for image in image_list:
        print(image)
        with open(image, 'rb') as image_file:
            my_image = Img(image_file)

            gps_latitude_ref = 'N'
            gps_longitude_ref = 'W'
            print("GPS")
            try:
                get_all = my_image.get_all()
                all_tag.append(get_all)
                # print(f"all_tag: {all_tag}")
                GPSExifData.GPS_latitude = dms_to_dd(my_image.gps_latitude, my_image.gps_latitude_ref)
                GPSExifData.GPS_longitude = dms_to_dd(my_image.gps_longitude, my_image.gps_longitude_ref)
            except:
                pass
    return all_tag


@app.get("/")
async def hello():
    return {"result": "Image to Map - Its working YES! This is a miracle!"}


@app.post("/exif_csv", tags=['files for downloading'])
async def create_csv(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    print(photo_list)
    df2 = pd.DataFrame(tags)
    stream = io.StringIO()
    df2.to_csv(stream, index=False, escapechar='\\')
    #, sep='\t'
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.csv"
    ######to empty the lists###########
    df2.iloc[0:0]
    tags.clear()
    photo_list.clear()
    ######delete folder######

    return response


@app.post("/exif_excel", tags=['files for downloading'])
async def create_excel(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = BackgroundTasks):
    folder_UUID = str(uuid.uuid1())

    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    print(photo_list)
    df4 = pd.DataFrame(tags)

    try:
        file_excel = io.BytesIO()
        writer = pd.ExcelWriter(file_excel, engine='xlsxwriter')
        df4.to_excel(writer, sheet_name='Sheet1')
        writer.close()
        file_excel.seek(0)
        xlsx_data = file_excel.getvalue()

        ####remove files after download######
        # background_tasks.add_task(os.remove, path)

        headers = {"Content-Disposition": f'attachment; filename={folder_UUID}.xlsx'}
        response = StreamingResponse(io.BytesIO(xlsx_data),
                                 media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                 headers=headers,
                                 status_code=200, background=background_tasks)
        ######to empty the lists###########
        df4.iloc[0:0]
        tags.clear()
        photo_list.clear()

        return response
    except:
        return "not ok"



@app.post("/exif_html_table", tags=['html for viewing'])
async def create_table(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    # output file path
    # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
    # path = temp_path+"/directory"
    path = temp_path + "/" + folder_UUID
    for file in files:
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df2 = pd.DataFrame(tags)
    stream = io.StringIO()
    html_table_image = df2.to_html(stream, index=False)
    ######to empty the lists###########
    df2.iloc[0:0]
    tags.clear()
    photo_list.clear()
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/html", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.html"

    return response


@app.post("/exif_json", tags=['json for viewing'])
async def create_json(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    # output file path
    # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
    path = temp_path + "/" + folder_UUID
    for file in files:
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df0 = pd.DataFrame(tags)
    stream = io.StringIO()
    #to_json --- orient="table" orient="columns" orient="index"  orient="records"  orient="split"
    df0.to_json(stream, orient="records")
    ######to empty the lists###########
    df0.iloc[0:0]
    tags.clear()
    photo_list.clear()
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/json", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.json"

    return response


@app.post("/exif_html_map", tags=['html for viewing'])
async def create_map(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    # print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    # print(photo_list)
    df5 = pd.DataFrame(tags)


    for x in range(len(df5.index)):
        # Name.append(GPSExifData.Image_name)

        if pd.isnull(df5['gps_latitude'].iloc[x]):

            print(f"empty exif, no coordinate ")
            Lat.append(0)
            Lon.append(0)
        else:
            Lat.append(dms_to_dd(df5.gps_latitude[x], df5.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df5.gps_longitude[x], df5.gps_longitude_ref[x]))
    df5["Latitude"] = Lat
    df5["Longitude"] = Lon
    df5["Name"] = Name
    first_column = df5.pop('Name')
    # insert column using insert(position,column_name,
    # first_column) function
    df5.insert(0, 'Name', first_column)

    # print(df7.Latitude, df7.Longitude)
    gdf = geopandas.GeoDataFrame(
        df5, geometry=geopandas.points_from_xy(df5.Longitude, df5.Latitude), crs="EPSG:4326")
    print(gdf.head())

    world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))

    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df5.Latitude[0], df5.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    #########create marker######
    for _, r in df5.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['datetime']),
                      icon=folium.Icon(icon="cloud"), ).add_to(m)

    ######to empty the lists###########
    df5.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    ######create html map#######
    html_map = m._repr_html_()
    response = StreamingResponse(iter([html_map]), media_type="text/html", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.html"

    return response


@app.post("/exif_shp", tags=['files for downloading'])
async def create_shp(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df7 = pd.DataFrame(tags)

    for x in range(len(df7.index)):
        # Name.append(GPSExifData.Image_name)
        if pd.isnull(df7['gps_latitude'].iloc[x]):
           print(f"empty exif, no coordinate ")
           Lat.append(0)
           Lon.append(0)
        else:
            Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
    df7["Latitude"] = Lat
    df7["Longitude"] = Lon
    df7["Name"] = Name
    first_column = df7.pop('Name')
    # df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # df7['datetime_'] = pd.to_datetime(df7.datetime_, utc=True)
    # df7['datetime_original_'] = pd.to_datetime(df7.datetime_original_, format='%Y-%m-%d', utc=True)
    # df7['datetime_digitized_'] = pd.to_datetime(df7.datetime_digitized_, format='%Y-%m-%d', utc=True)
    # df7['datetime_'] = df7['datetime'].dt.strftime("%Y-%m-%d")
    # df7['datetime_original_'] = df7['datetime_original'].dt.strftime("%Y-%m-%d")
    # df7['datetime_digitized_'] = df7['datetime_digitized'].dt.strftime("%Y-%m-%d")
    del df7["datetime"]
    del df7["datetime_original"]
    del df7["datetime_digitized"]
    # df7.pop("gps_datestamp")
    # del df7["gps_datestamp"]
    del df7["flash"]
    del df7["gps_latitude"]
    del df7["gps_longitude"]
    # df7.pop("flash")
    df7.insert(0, 'Name', first_column)

    # print(df7.Latitude, df7.Longitude)
    gdf = geopandas.GeoDataFrame(
        df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
    print(gdf.head())

    world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))

    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df7.Latitude[0], df7.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    #########create marker######
    for _, r in df7.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                      icon=folium.Icon(icon="cloud"), ).add_to(m)
    df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
    # df7.to_csv(f"{folder_UUID}/out.csv", index=True, escapechar='\\')

    ### datetime datetime_original  datetime_digitized

    #######create shp files - point######
    gdf2 = geopandas.GeoDataFrame()
    gdf2["Name"] = gdf["Name"]
    gdf2["geometry"] = gdf["geometry"]
    gdf2["Altitude"] = gdf["gps_altitude"]
    gdf2["Direction"] = gdf["gps_img_direction"]
    gdf2["Latitude"] = gdf["Latitude"]
    gdf2["Longitude"] = gdf["Longitude"]
    gdf2["Model"] = gdf["model"]
    # print(gdf2.head())
    print(fiona.supported_drivers)
    fiona.supported_drivers['KML'] = 'rw'
    fiona.supported_drivers['DXF'] = 'rw'
    path_zip = os.path.join(path, "Shp_files")
    try:
        os.mkdir(path_zip)
    except OSError as error:
        print(error)

    gdf2.to_file(path + '/points.kml', driver='KML', crs="EPSG:4326")
    gdf2.to_file(path_zip + '/points.shp', crs="EPSG:4326")
    gdf2.to_file(path + "/points.geojson", driver="GeoJSON")
    gdf2.to_file(path + "/points.gpx", driver="GPX", GPX_USE_EXTENSIONS="Yes")

    path_zip_ID = f"{temp_path}/{folder_UUID}/Shp_files"
    path = f"{temp_path}/{folder_UUID}/"

    entries = Path(path_zip_ID)
    zip_filename = 'compressSHP.zip'
    zip_path = os.path.join(os.path.dirname(path), zip_filename)
    with ZipFile(zip_path,  mode='w') as myzip:
        for entry in entries.iterdir():
            # print(f"name: {entry.name}")
            # print(f"name: {entry}")
            myzip.write(entry, arcname=entry.name)
            # myzip.close()

    print(gdf.head())
    ######to empty the lists###########
    df7.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    file_path = f"{path}/{zip_filename}"
    response = FileResponse(path=file_path, filename=zip_filename)

    return response


@app.post("/exif_geojson", tags=['files for downloading'])
async def create_geojson(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df8 = pd.DataFrame(tags)

    for x in range(len(df8.index)):
        # Name.append(GPSExifData.Image_name)
        if pd.isnull(df8['gps_latitude'].iloc[x]):
           print(f"empty exif, no coordinate ")
           Lat.append(0)
           Lon.append(0)
        else:
            Lat.append(dms_to_dd(df8.gps_latitude[x], df8.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df8.gps_longitude[x], df8.gps_longitude_ref[x]))
    df8["Latitude"] = Lat
    df8["Longitude"] = Lon
    df8["Name"] = Name
    first_column = df8.pop('Name')
    # df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # df7['datetime_'] = pd.to_datetime(df7.datetime_, utc=True)
    # df7['datetime_original_'] = pd.to_datetime(df7.datetime_original_, format='%Y-%m-%d', utc=True)
    # df7['datetime_digitized_'] = pd.to_datetime(df7.datetime_digitized_, format='%Y-%m-%d', utc=True)
    # df7['datetime_'] = df7['datetime'].dt.strftime("%Y-%m-%d")
    # df7['datetime_original_'] = df7['datetime_original'].dt.strftime("%Y-%m-%d")
    # df7['datetime_digitized_'] = df7['datetime_digitized'].dt.strftime("%Y-%m-%d")
    del df8["datetime"]
    del df8["datetime_original"]
    del df8["datetime_digitized"]
    # df7.pop("gps_datestamp")
    # del df7["gps_datestamp"]
    del df8["flash"]
    del df8["gps_latitude"]
    del df8["gps_longitude"]
    # df7.pop("flash")
    df8.insert(0, 'Name', first_column)

    # print(df7.Latitude, df7.Longitude)
    gdf = geopandas.GeoDataFrame(
        df8, geometry=geopandas.points_from_xy(df8.Longitude, df8.Latitude), crs="EPSG:4326")
    print(gdf.head())

    world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))

    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df8.Latitude[0], df8.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    #########create marker######
    for _, r in df8.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                      icon=folium.Icon(icon="cloud"), ).add_to(m)
    # df8.to_csv(path + '/out.csv', index=True, escapechar='\\')

    ### datetime datetime_original  datetime_digitized

    #######create shp files - point######
    gdf2 = geopandas.GeoDataFrame()
    gdf2["Name"] = gdf["Name"]
    gdf2["geometry"] = gdf["geometry"]
    gdf2["Altitude"] = gdf["gps_altitude"]
    gdf2["Direction"] = gdf["gps_img_direction"]
    gdf2["Latitude"] = gdf["Latitude"]
    gdf2["Longitude"] = gdf["Longitude"]
    gdf2["Model"] = gdf["model"]
    # print(gdf2.head())
    print(fiona.supported_drivers)
    fiona.supported_drivers['KML'] = 'rw'
    fiona.supported_drivers['DXF'] = 'rw'
    #####Create folder for shp files#####
    # path_zip = os.path.join(path, "Shp_files")
    # try:
    #     os.mkdir(path_zip)
    # except OSError as error:
    #     print(error)

    # gdf2.to_file(path + '/points.kml', driver='KML', crs="EPSG:4326")
    # gdf2.to_file(path_zip + '/points.shp', crs="EPSG:4326")
    name = "points.geojson"
    filename = gdf2.to_file(path + "/points.geojson", driver="GeoJSON")
    # gdf2.to_file(path + "/points.gpx", driver="GPX", GPX_USE_EXTENSIONS="Yes")

    # path_zip_ID = f"/Users/kalin/PycharmProjects/ImageToMap/outFiles/{folder_UUID}/Shp_files"
    path = f"{temp_path}/{folder_UUID}/"
    #
    # entries = Path(path_zip_ID)
    # zip_filename = 'compressSHP.zip'
    # zip_path = os.path.join(os.path.dirname(path), zip_filename)
    # with ZipFile(zip_path,  mode='w') as myzip:
    #     for entry in entries.iterdir():
    #         # print(f"name: {entry.name}")
    #         # print(f"name: {entry}")
    #         myzip.write(entry, arcname=entry.name)
    #         # myzip.close()

    print(gdf.head())
    ######to empty the lists###########
    df8.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    file_path = f"{path}{name}"
    # print(f"file_path {file_path}")
    response = FileResponse(path=file_path, filename=name)

    return response


@app.post("/exif_kml", tags=['files for downloading'])
async def create_kml(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df9 = pd.DataFrame(tags)

    for x in range(len(df9.index)):
        # Name.append(GPSExifData.Image_name)
        if pd.isnull(df9['gps_latitude'].iloc[x]):
           print(f"empty exif, no coordinate ")
           Lat.append(0)
           Lon.append(0)
        else:
            Lat.append(dms_to_dd(df9.gps_latitude[x], df9.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df9.gps_longitude[x], df9.gps_longitude_ref[x]))
    df9["Latitude"] = Lat
    df9["Longitude"] = Lon
    df9["Name"] = Name
    first_column = df9.pop('Name')
    # df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # df7['datetime_'] = pd.to_datetime(df7.datetime_, utc=True)
    # df7['datetime_original_'] = pd.to_datetime(df7.datetime_original_, format='%Y-%m-%d', utc=True)
    # df7['datetime_digitized_'] = pd.to_datetime(df7.datetime_digitized_, format='%Y-%m-%d', utc=True)
    # df7['datetime_'] = df7['datetime'].dt.strftime("%Y-%m-%d")
    # df7['datetime_original_'] = df7['datetime_original'].dt.strftime("%Y-%m-%d")
    # df7['datetime_digitized_'] = df7['datetime_digitized'].dt.strftime("%Y-%m-%d")
    del df9["datetime"]
    del df9["datetime_original"]
    del df9["datetime_digitized"]
    # df7.pop("gps_datestamp")
    # del df7["gps_datestamp"]
    del df9["flash"]
    del df9["gps_latitude"]
    del df9["gps_longitude"]
    # df7.pop("flash")
    df9.insert(0, 'Name', first_column)

    # print(df7.Latitude, df7.Longitude)
    gdf = geopandas.GeoDataFrame(
        df9, geometry=geopandas.points_from_xy(df9.Longitude, df9.Latitude), crs="EPSG:4326")
    print(gdf.head())

    world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))

    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df9.Latitude[0], df9.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    #########create marker######
    for _, r in df9.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                      icon=folium.Icon(icon="cloud"), ).add_to(m)
    # df9.to_csv(path + '/out.csv', index=True, escapechar='\\')

    ### datetime datetime_original  datetime_digitized

    #######create shp files - point######
    gdf2 = geopandas.GeoDataFrame()
    gdf2["Name"] = gdf["Name"]
    gdf2["geometry"] = gdf["geometry"]
    gdf2["Altitude"] = gdf["gps_altitude"]
    gdf2["Direction"] = gdf["gps_img_direction"]
    gdf2["Latitude"] = gdf["Latitude"]
    gdf2["Longitude"] = gdf["Longitude"]
    gdf2["Model"] = gdf["model"]
    # print(gdf2.head())
    print(fiona.supported_drivers)
    fiona.supported_drivers['KML'] = 'rw'
    # fiona.supported_drivers['DXF'] = 'rw'
    #####Create folder for shp files#####
    # path_zip = os.path.join(path, "Shp_files")
    # try:
    #     os.mkdir(path_zip)
    # except OSError as error:
    #     print(error)
    name = "points.kml"
    filename = gdf2.to_file(path + '/points.kml', driver='KML', crs="EPSG:4326")
    # gdf2.to_file(path_zip + '/points.shp', crs="EPSG:4326")

    # filename = gdf2.to_file(path + "/points.geojson", driver="GeoJSON")
    # gdf2.to_file(path + "/points.gpx", driver="GPX", GPX_USE_EXTENSIONS="Yes")

    # path_zip_ID = f"/Users/kalin/PycharmProjects/ImageToMap/outFiles/{folder_UUID}/Shp_files"
    path = f"{temp_path}/{folder_UUID}/"

    #
    # entries = Path(path_zip_ID)
    # zip_filename = 'compressSHP.zip'
    # zip_path = os.path.join(os.path.dirname(path), zip_filename)
    # with ZipFile(zip_path,  mode='w') as myzip:
    #     for entry in entries.iterdir():
    #         # print(f"name: {entry.name}")
    #         # print(f"name: {entry}")
    #         myzip.write(entry, arcname=entry.name)
    #         # myzip.close()

    print(gdf.head())
    ######to empty the lists###########
    df9.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    file_path = f"{path}{name}"
    # print(f"file_path {file_path}")
    response = FileResponse(path=file_path, filename=name)

    return response


@app.post("/exif_gpx", tags=['files for downloading'])
async def create_gpx(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df10 = pd.DataFrame(tags)

    for x in range(len(df10.index)):
        # Name.append(GPSExifData.Image_name)
        if pd.isnull(df10['gps_latitude'].iloc[x]):
           print(f"empty exif, no coordinate ")
           Lat.append(0)
           Lon.append(0)
        else:
            Lat.append(dms_to_dd(df10.gps_latitude[x], df10.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df10.gps_longitude[x], df10.gps_longitude_ref[x]))
    df10["Latitude"] = Lat
    df10["Longitude"] = Lon
    df10["Name"] = Name
    first_column = df10.pop('Name')
    # df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # df7['datetime_'] = pd.to_datetime(df7.datetime_, utc=True)
    # df7['datetime_original_'] = pd.to_datetime(df7.datetime_original_, format='%Y-%m-%d', utc=True)
    # df7['datetime_digitized_'] = pd.to_datetime(df7.datetime_digitized_, format='%Y-%m-%d', utc=True)
    # df7['datetime_'] = df7['datetime'].dt.strftime("%Y-%m-%d")
    # df7['datetime_original_'] = df7['datetime_original'].dt.strftime("%Y-%m-%d")
    # df7['datetime_digitized_'] = df7['datetime_digitized'].dt.strftime("%Y-%m-%d")
    del df10["datetime"]
    del df10["datetime_original"]
    del df10["datetime_digitized"]
    # df7.pop("gps_datestamp")
    # del df7["gps_datestamp"]
    del df10["flash"]
    del df10["gps_latitude"]
    del df10["gps_longitude"]
    # df7.pop("flash")
    df10.insert(0, 'Name', first_column)

    # print(df7.Latitude, df7.Longitude)
    gdf = geopandas.GeoDataFrame(
        df10, geometry=geopandas.points_from_xy(df10.Longitude, df10.Latitude), crs="EPSG:4326")
    print(gdf.head())

    world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))

    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df10.Latitude[0], df10.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    #########create marker######
    for _, r in df10.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                      icon=folium.Icon(icon="cloud"), ).add_to(m)
    # df8.to_csv(path + '/out.csv', index=True, escapechar='\\')

    ### datetime datetime_original  datetime_digitized

    #######create shp files - point######
    gdf2 = geopandas.GeoDataFrame()
    gdf2["Name"] = gdf["Name"]
    gdf2["geometry"] = gdf["geometry"]
    gdf2["Altitude"] = gdf["gps_altitude"]
    gdf2["Direction"] = gdf["gps_img_direction"]
    gdf2["Latitude"] = gdf["Latitude"]
    gdf2["Longitude"] = gdf["Longitude"]
    gdf2["Model"] = gdf["model"]
    # print(gdf2.head())
    print(fiona.supported_drivers)
    # fiona.supported_drivers['KML'] = 'rw'
    # fiona.supported_drivers['DXF'] = 'rw'
    #####Create folder for shp files#####
    # path_zip = os.path.join(path, "Shp_files")
    # try:
    #     os.mkdir(path_zip)
    # except OSError as error:
    #     print(error)

    # gdf2.to_file(path + '/points.kml', driver='KML', crs="EPSG:4326")
    # gdf2.to_file(path_zip + '/points.shp', crs="EPSG:4326")
    name = "points.gpx"
    # filename = gdf2.to_file(path + "/points.geojson", driver="GeoJSON")
    filename = gdf2.to_file(path + "/points.gpx", driver="GPX", GPX_USE_EXTENSIONS="Yes")

    # path_zip_ID = f"/Users/kalin/PycharmProjects/ImageToMap/outFiles/{folder_UUID}/Shp_files"
    path = f"{temp_path}/{folder_UUID}/"
    #
    # entries = Path(path_zip_ID)
    # zip_filename = 'compressSHP.zip'
    # zip_path = os.path.join(os.path.dirname(path), zip_filename)
    # with ZipFile(zip_path,  mode='w') as myzip:
    #     for entry in entries.iterdir():
    #         # print(f"name: {entry.name}")
    #         # print(f"name: {entry}")
    #         myzip.write(entry, arcname=entry.name)
    #         # myzip.close()

    print(gdf.head())
    ######to empty the lists###########
    df10.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    file_path = f"{path}{name}"
    # print(f"file_path {file_path}")
    response = FileResponse(path=file_path, filename=name)

    return response


@app.get("/files_info", tags=['admin tools'])
async def files_size_mb():
    result = []
    try:
        total_size = 0
        for path, dirs, files in os.walk(temp_path):
            for f in files:
                fp = os.path.join(path, f)
                total_size += os.path.getsize(fp)
        size_MB = str("%.2f" % float(total_size/ 1024 ** 2))
        result.append(f"Directory size {folder_name}: {size_MB} MB")
        return result
    except:
        return {"Empty folder "}


@app.delete("/delete_all_files", tags=['admin tools'])
async def delete_all_files():
    try:
        delete_folder(temp_path)
        return {"All files is gone in folder": f"{temp_path}"}
    except:
        return {"The folder is empty": f"{temp_path}"}



def raise_exception():
    return HTTPException(status_code=404,
                         detail="Input is Not valid!",
                         headers={"X-Header_Error": f"Nothing to be seen"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True, log_level="info", workers=2)

print('Ready')
