# location_annotation_with_openstreetmap
This is an easy-to-use Python package for annotating location data with OpenStreetMap Point-of-interest tags. It provides a solution for researchers to adding additional layer of context information to location data at large scale in an automatic way. For example, the input can be pairs of coordinates (lat, lon), and the output are types of places of the input locations, such as "gym", "restaurant", "university", "office", etc. Annotation using this package incurs no cost when this package downloads and uses free POI data from [Geofabrik](https://www.geofabrik.de/) that reflect daily changes from [OpenStreetMap](https://en.wikipedia.org/wiki/OpenStreetMap). For questions about this package, please leave an issue or contact li.jix@northeastern.edu .

### Two general steps
**1. Download and create a geofabrik POI database in local system**  
**2. Annotate location data using the POI database**  
    
This package integrates the geodf and dist functions from the GPS2space package (https://gps2space.readthedocs.io/en/latest/). 

## Dependencies
- geopandas
- fiona
- gps2space
- tqdm
- Python >= 3.7

## Demo
A demo on how to use this package can be found in the [jupyter notebook](https://github.com/rexli999/location_annotation_with_openstreetmap/blob/main/package_demo.ipynb).

## Intall package
```bash
pip install osm_annotation
```

## Import package
```bash
from osm_annotation import geofabrik_database, semantic_annotation
```

## Build a local geofabrik POI database
```python
# database_folder_path is the path to a local folder where you want to build the database. The disk should have at least 150 GB.
geofabrik_database.build(database_folder_path)
```

## Annotate location data  

There are three annotation method options:  

|Method|Description|TIME|Pro|Con|
|---|---|---|---|---|
|annotate_single_point(lat, lon)| annotate a single point| ~3 hours/point|return distances to all POI types| time-consuming. Method 3 is recommended for batch of points|
|annotate_single_shape(lat_list, lon_list)| annotate single shape (e.g., bounding box, polygon)|~30 min/shape| **most accurate method** | need a set of points define the query shape |
|annotate_batch_points(dataframe, latitude_colname, longitude_colname)| annotate a batch of points (usually centroids of places)|~3 hours/batch of points| **fastest method**. Fit for annotating many centroids of places simultaneously.| return the label of the nearest POI and the distance.   |
  
		
### Initialization
```python
semantic_annotator = SemanticAnnotator(database_folder_path)
```


### Example of Method 1
```python
# coordinates of Fenway Park in Boston
centroid_latitude = 42.34653831212525
centroid_longitude = -71.09724395926423
semantic_annotator.annotate_single_point(centroid_latitude, centroid_longitude)
```

Returned result is a json file with
- matched_labels: semantic label matched with the query point
- min_distance: the distance from the query point to the matched POI, in meters
- distances_to_pois: distance to other types of POIs
> {'matched_labels': 'recreational;outdoor;pitch (polygon)',
 'min_distance': 6.169761255410299,
 'distances_to_pois': {'busines;busines;company (polygon)': 326501.593160387,
  'busines;busines;convention_center (polygon)': 2682942.101031607,
  'busines;busines;factory (polygon)': 3612.955363467255,
  'busines;busines;industrial (polygon)': 486.88772114370636,
  'busines;busines;office (polygon)': 932.2980449124797,
  'commercial;food;bakery (point)': 738.1374807550822,
> ...
> }


### Example of Method 2
```python
# bounding box (NW corner,NE corner, SE corner, SW corner) of Museum of Fine Arts in Boston
lat_list = [42.33969558839377, 42.34039653732734, 42.339235761638996, 42.33847311473655]
lon_list = [-71.09563225696323, -71.09348529667446, -71.09270768730832, -71.0948470612041]
semantic_annotator.annotate_single_shape(lat_list, lon_list)
```

Returned result is a json file with
- matched_labels: semantic labels matched with the query shape
- point_labels: semantic labels of point POI matched with the query shape
- poly_labels: semantic labels of polygon POI matched with the query shape
- matched_geometries: geometries of POIs matched with the query shape
> {'matched_labels': ['commercial;food;cafe (point)',
  'commercial;shopping;shop (point)',
  'commercial;leisure;museum (polygon)',
  'service;transportation;parking (polygon)',
  'recreational;outdoor;nature (polygon)'],
 'point_labels': ['commercial;food;cafe (point)',
  'commercial;shopping;shop (point)'],
 'poly_labels': ['commercial;leisure;museum (polygon)',
  'recreational;outdoor;nature (polygon)',
  'service;transportation;parking (polygon)'],
 'matched_geometries': [<shapely.geometry.point.Point at 0x2b8b25338410>,
  <shapely.geometry.polygon.Polygon at 0x2b8b25353b10>,
  <shapely.geometry.point.Point at 0x2b8b253415d0>,
  <shapely.geometry.polygon.Polygon at 0x2b8b250b0910>,
  <shapely.geometry.polygon.Polygon at 0x2b8b25331690>]}



### Example of Method 3
```python
# library, cafe, gym, and train station around the Northeastern University campus
locations = [[42.33833,-71.08795], # library
             [42.33909,-71.08758], # cafe
             [42.34033,-71.09038], # gym
             [42.33661, -71.08944]] # train station
location_dataframe = pd.DataFrame(data = locations, columns = ['latitude', 'longitude'])
semantic_annotator.annotate_batch_points(dataframe = location_dataframe, latitude_colname = 'latitude', longitude_colname = 'longitude')
```

Returned result is a dataframe with
- matched_labels: semantic labels matched with the query points
- min_distance: the distance from the query point to the matched POI, in meters

![alt text](https://github.com/rexli999/location_annotation_with_openstreetmap/blob/main/batch_results.png "batch result")
