"""Benchmarking tests"""
import timeit
import random
import getpass
import time
import os
from datetime import datetime
from collections import defaultdict, Counter
from qgis.core import *
from PyQt4.QtCore import QVariant
from osgeo import gdal
#gdal.PushErrorHandler('CPLQuietErrorHandler')

import hgwnames
import setup
import layer
import osmxml
import osm
from download import ProgressBar
from catatom2osm import QgsSingleton
qgs = QgsSingleton()

N = 1
MS = 1000
BASEPATH = '/home/{}/temp/catastro/'.format(getpass.getuser())

class BaseTimer(object):

    def test(self, func):
        p = func.__name__
        if p.startswith('test_'): p = p[5:]
        t = timeit.timeit(func, number=N) * MS
        print self.obj.__class__.__name__ + '.' + p + ': ' + str(t)
    
    def run(self):
        set_up = None
        for p in dir(self):
            if p == 'set_up':
                set_up = getattr(self, p)
        for p in dir(self):
            if p.startswith('test_'):
                if set_up:
                    set_up()
                self.test(getattr(self, p))

class TimerBaseLayer(BaseTimer):

    def __init__(self):
        self.fixture = QgsVectorLayer('test/building.gml', 'building', 'ogr')
        self.obj = layer.BaseLayer("Polygon", "test", "memory")
        
    def test_append(self):
        self.obj.append(self.fixture)
    
    def test_reproject(self):
        self.obj.reproject()


class TimerPolygonLayer(BaseTimer):

    def __init__(self):
        self.fixture = QgsVectorLayer('test/cons.shp', 'building', 'ogr')
        self.obj = layer.PolygonLayer('Polygon', 'building', 'memory')
        self.obj.append(self.fixture, rename='')

    def test_explode_multi_parts(self):
        self.obj.explode_multi_parts()
        
    def test_get_vertices(self):
        self.obj.get_vertices()


class TimerAddressLayer(BaseTimer):

    def __init__(self):
        address_fn = 'test/address.gml'
        address_fn = BASEPATH + '{0}/A.ES.SDGC.AD.{0}.gml'.format('38900')
        self.address_gml = QgsVectorLayer(address_fn, 'address', 'ogr')
        self.tn_gml = QgsVectorLayer(address_fn + '|layername=thoroughfarename', 'tn', 'ogr')
        self.pd_gml = QgsVectorLayer(address_fn + '|layername=postaldescriptor', 'pd', 'ogr')
        self.au_gml = QgsVectorLayer(address_fn + '|layername=adminUnitname', 'au', 'ogr')
        assert(self.address_gml.isValid())
        assert(self.tn_gml.isValid())
        assert(self.pd_gml.isValid())
        assert(self.au_gml.isValid())
        
    def set_up(self):
        self.obj = layer.AddressLayer()
        self.obj.append(self.address_gml)
        self.obj.join_field(self.tn_gml, 'TN_id', 'gml_id', ['text'], 'TN_')
        self.obj.join_field(self.au_gml, 'AU_id', 'gml_id', ['text'], 'AU_')
        self.obj.join_field(self.pd_gml, 'PD_id', 'gml_id', ['postCode'])
        
    def test_delete_addres_without_number1(self):
        to_clean = [f.id for f in self.obj.getFeatures() if f['designator'] == 'S-N']
        self.obj.deleteFeatures(to_clean)

    def test_delete_addres_without_number2(self):
        to_clean = [f.id() for f in self.obj.search("designator = 'S-N'")]
        self.obj.deleteFeatures(to_clean)


class TimerAddressLayer2(BaseTimer):

    def __init__(self):
        mun = '38012'
        address_fn = 'test/address.gml'
        address_fn = BASEPATH + '{0}/A.ES.SDGC.AD.{0}.gml'.format(mun)
        self.address_gml = QgsVectorLayer(address_fn, 'address', 'ogr')
        self.tn_gml = QgsVectorLayer(address_fn + '|layername=thoroughfarename', 'tn', 'ogr')
        self.pd_gml = QgsVectorLayer(address_fn + '|layername=postaldescriptor', 'pd', 'ogr')
        self.au_gml = QgsVectorLayer(address_fn + '|layername=adminUnitname', 'au', 'ogr')
        assert(self.address_gml.isValid())
        assert(self.tn_gml.isValid())
        assert(self.pd_gml.isValid())
        assert(self.au_gml.isValid())
        osm_path = BASEPATH + mun + '/current_highway.osm'
        fo = open(osm_path, 'r')
        highway_osm = osmxml.deserialize(fo)
        self.highway = layer.HighwayLayer()
        self.highway.read_from_osm(highway_osm)
        self.highway.reproject(self.address_gml.crs())
        self.obj = layer.AddressLayer()
        self.obj.append(self.address_gml)
        self.obj.join_field(self.tn_gml, 'TN_id', 'gml_id', ['text'], 'TN_')
        self.obj.join_field(self.au_gml, 'AU_id', 'gml_id', ['text'], 'AU_')
        self.obj.join_field(self.pd_gml, 'PD_id', 'gml_id', ['postCode'])
        fid = random.randrange(self.obj.featureCount())
        request = QgsFeatureRequest().setFilterFids([fid])
        self.ad = self.obj.getFeatures(request).next()
        self.index = self.highway.get_index()
        self.features = {feat.id(): feat for feat in self.highway.getFeatures()}
        
    def test_get_highway_names1a(self):
        query = self.obj.search("TN_text='%s'" % self.ad['TN_text'])
        self.points = [f.geometry().asPoint() for f in query]

    def test_get_highway_names1b(self):
        bbox = QgsGeometry().fromMultiPoint(self.points).boundingBox()
        self.choices = [self.features[fid]['name'] for fid in self.index.intersects(bbox)]

    def test_get_highway_names1c(self):
        name = hgwnames.match(self.ad['TN_text'], self.choices)

    def _test_get_highway_names1(self):
        highway_names = {}
        for feat in self.obj.getFeatures():
            name = feat['TN_text']
            if name not in highway_names:
                query = self.obj.search("TN_text='%s'" % self.ad['TN_text'])
                points = [f.geometry().asPoint() for f in query]
                bbox = QgsGeometry().fromMultiPoint(points).boundingBox()
                choices = [self.features[fid]['name'] for fid in self.index.intersects(bbox)]
                name = hgwnames.match(name, choices)

    def test_get_highway_names2a(self):
        self.highway_names = defaultdict(list)
        for feat in self.obj.getFeatures():
            self.highway_names[feat['TN_text']].append(feat.geometry().asPoint())

    def test_get_highway_names2b(self):
        for name, points in self.highway_names.items():
            bbox = QgsGeometry().fromMultiPoint(points).boundingBox()
            choices = [self.features[fid]['name'] for fid in self.index.intersects(bbox)]
            self.highway_names[name] = hgwnames.match(name, choices)

    def test_get_highway_names2(self):
        """127x faster than test_get_highway_names1"""
        highway_names = defaultdict(list)
        for feat in self.obj.getFeatures():
            highway_names[feat['TN_text']].append(feat.geometry().asPoint())
        for name, points in highway_names.items():
            bbox = QgsGeometry().fromMultiPoint(points).boundingBox()
            choices = [self.features[fid]['name'] for fid in self.index.intersects(bbox)]
            highway_names[name] = hgwnames.match(name, choices)


class TimerConsLayer(BaseTimer):

    def __init__(self):
        self.obj = layer.ConsLayer()
        mun = '38900'
        building_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.building.gml'.format(mun)
        buildingpart_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.buildingpart.gml'.format(mun)
        other_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.otherconstruction.gml'.format(mun)
        self.building_gml = QgsVectorLayer(building_fn, 'building', 'ogr')
        self.obj.append(self.building_gml)
        self.part_gml = QgsVectorLayer(buildingpart_fn, 'buildingpart', 'ogr')
        self.other_gml = QgsVectorLayer(other_fn, 'otherconstruction', 'ogr')
        QgsVectorFileWriter.writeAsVectorFormat(self.building_gml, 'temp.shp', "utf-8",
                self.building_gml.crs(), 'ESRI Shapefile')
        self.building_shp = QgsVectorLayer('temp.shp', 'building', 'ogr')
        c = self.building_gml.featureCount()
        #self.fids = [int(c*0.5) + i for i in range(50)]
        """
        self.zone = self.zoning_gml.getFeatures().next()
        self.request = QgsFeatureRequest().setFilterFids(self.fids)
        #self.test(self.get_features)
        #self.test(self.get_index)
        #self.fids = self.index.intersects(self.zone.geometry().boundingBox())
        osm_path = BASEPATH + mun + '/current_building.osm'
        fo = open(osm_path, 'r')
        self.current_bu_osm = osmxml.deserialize(fo)
        self.obj.reproject()
        print 'Seleccionando {} edificios de {}'.format(len(self.fids), c)
        self.test(self.get_fids_by_loop)
        """
        self.test(self.get_features)
        #self.test(self.get_index)
        self.test(self.get_index_shp)
        print '5 /', self.building_shp.featureCount()
        self.fids = [random.randrange(c) for i in range(5)]
        self.test(self.get_fids_by_dict_mem)
        self.test(self.get_fids_by_filter_shp)
        self.test(self.get_fids_by_filter_mem)
        print '50 /', self.building_shp.featureCount()
        self.fids = [random.randrange(c) for i in range(50)]
        self.test(self.get_fids_by_dict_mem)
        self.test(self.get_fids_by_filter_shp)
        self.test(self.get_fids_by_filter_mem)
        print '500 /', self.building_shp.featureCount()
        self.fids = [random.randrange(c) for i in range(500)]
        self.test(self.get_fids_by_dict_mem)
        self.test(self.get_fids_by_filter_shp)
        self.test(self.get_fids_by_filter_mem)
        print '5000 /', self.building_shp.featureCount()
        self.fids = [random.randrange(c) for i in range(5000)]
        self.test(self.get_fids_by_dict_mem)
        self.test(self.get_fids_by_filter_shp)
        self.test(self.get_fids_by_filter_mem)
        """
        self.test(self.get_fids_by_loop_mem)
        self.test(self.get_fid_by_fid)
        self.test(self.get_fids_by_select)
        self.test(self.get_fid_by_fid_mem)
        self.test(self.get_fids_by_select_mem)
        """
        QgsVectorFileWriter.deleteShapeFile('temp.shp')

    def zoning_histogram(self):
        index = QgsSpatialIndex(self.building_gml.getFeatures())
        c = {
            'MANZANA': [],
            'POLIGONO': []
        }
        for t in ('MANZANA', 'POLIGONO'):
            exp = QgsExpression("levelName = '(1:{} )'".format(t))
            request = QgsFeatureRequest(exp)
            for zone in self.zoning_gml.getFeatures(request):
                fids = index.intersects(zone.geometry().boundingBox())
                c[t].append(len(fids))
            print t, min(c[t]), max(c[t])
            print Counter(c[t])
    
    def get_features(self):
        """
        9K buildings 60 ms
        32K buildings 196 ms
        123K buildings 814 ms
        """
        self.features = {f.id(): f for f in self.obj.getFeatures()}
    
    def get_index(self):
        self.index = QgsSpatialIndex(self.building_gml.getFeatures())
        
    def get_index_shp(self):
        """3x faster than get_index (gml)"""
        self.index_shp = QgsSpatialIndex(self.building_shp.getFeatures())

    def get_fids_by_loop(self):
        """
        constant with the number of elements to select
        constant with the position of the elements to select
        linear with the size of the layer
        38012 (10/1972): 4x faster than get_fids_by_filter
        38012 (57/1972): 15x faster than get_fids_by_filter
        38012 (100/1972): 37x faster than get fids_by_filter
        38012 (1000/1972): 246x faster than get fids_by_filter
        38006 (10/9319): 3,6x faster than get fids_by_filter
        38006 (100/9319): 36x faster than get fids_by_filter
        """
        [f for f in self.building_gml.getFeatures() if f.id() in set(self.fids)]

    def get_fids_by_loop2(self):
        """Winner for ogr layers 1.25x faster than get_fids_by_loop"""
        s = set(self.fids)
        [f for f in self.building_gml.getFeatures() if f.id() in s]
        
    def get_fids_by_filter(self):
        """
        grows exp10 with the number of elements to select
        grows log with the position of the elements to select
        grows linear with the size of the layer
        38012 (1/1972): 1,32x faster than get_fids_by_loop 
        38006 (1/9319): 1,7x faster than get_fids_by_loop
        08900 (1/70354): 2x faster than get_fids_by_loop
        28900 (1/122921): 4x faster than get_fids_by_loop
        """
        request = QgsFeatureRequest().setFilterFids(self.fids)
        [f for f in self.building_gml.getFeatures(request)]
    
    def get_fids_by_filter_shp(self):
        """
        Very fast. 
        Example select 4 randon features in 08900 (70K buildings)
        10x get_fids_by_filter_mem
        4000x get_fids_by_loop2
        9000x get_fids_by_filter
        Linear with size of selection
        Linear with layer size
        Constant with position of elements to select
        """
        request = QgsFeatureRequest().setFilterFids(self.fids)
        [f for f in self.building_shp.getFeatures(request)]

    def get_fids_by_loop_mem(self):
        """10x slower or more than get_fids_by_filter_mem"""
        [f for f in self.obj.getFeatures() if f.id() in set(self.fids)]
        
    def get_fids_by_loop_mem2(self):
        """
        Faster than get_fids_by_loop_mem (depending on the size of the 
        selecction), but still slower than get_fids_by_filter_mem
        """
        s = set(self.fids)
        [f for f in self.obj.getFeatures() if f.id() in s]
        
    def get_fids_by_dict_mem(self):
        """Absolute winner. 70x faster than get_fids_by_filter_shp"""
        [self.features[i] for i in self.fids]

    def get_fids_by_filter_mem(self):
        """
        When the number of elements to select is very big, is faster than get_fids_by_filter_shp
        Don't suffer grown exp10 with the number of elements to select of gmls
        200x faster than get_fids_by_loop
        """
        request = QgsFeatureRequest().setFilterFids(self.fids)
        [f for f in self.obj.getFeatures(request)]
    
    def get_fid_by_fid(self):
        """
        constant with the position of the elements to select
        grows brutally with the number of elements to select
        """
        r = []
        for fid in self.fids:
            request = QgsFeatureRequest().setFilterFids([fid])
            r.append(self.building_gml.getFeatures(request))

    def get_fid_by_fid_mem(self):
        """Initially the faster, but grows quickly with selection size"""
        r = []
        for fid in self.fids:
            request = QgsFeatureRequest().setFilterFids([fid])
            r.append(self.obj.getFeatures(request))

    def get_fids_by_select(self):
        """get_fids_by_filter ~= get_fids_by_select"""
        self.building_gml.setSelectedFeatures(self.fids)
        [f for f in self.building_gml.selectedFeatures()]
    
    def get_fids_by_select_mem(self):
        """Initially fast, but similar when selection size grows"""
        self.obj.setSelectedFeatures(self.fids)
        [f for f in self.obj.selectedFeatures()]

    def _test_append_zone(self):
        processed = []
        it = self.zoning_gml.getFeatures()
        for i in range(10):
            zone = it.next()
            self.obj.append_zone2(self.building, self.zone, processed)

    def _test_conflate2(self):
        delete = True
        index = self.obj.get_index()
        num_buildings = 0
        conflicts = 0
        to_clean = set()
        for el in self.current_bu_osm.elements:
            poly = None
            if el.type == 'way' and el.is_closed() and 'building' in el.tags:
                poly = [[map(layer.Point, el.geometry())]]
            elif el.type == 'relation' and 'building' in el.tags:
                poly = [[map(layer.Point, w)] for w in el.outer_geometry()]
            if poly:
                num_buildings += 1
                geom = QgsGeometry().fromMultiPolygon(poly)
                if geom.isGeosValid():
                    conflict = False
                    fids = index.intersects(geom.boundingBox())
                    self.obj.setSelectedFeatures(fids)
                    for feat in self.obj.selectedFeatures():
                        fg = feat.geometry()
                        if geom.contains(fg) or fg.contains(geom) \
                                or geom.overlaps(fg):
                            conflict = True
                            conflicts += 1
                            break
                    if delete and not conflict:
                        to_clean.add(el)
                    if not delete and conflict:
                        el.tags['conflict'] = 'yes'
        print "Detected {} conflicts in {} buildings from OSM".format(conflicts, num_buildings)


    def _test_conflate(self):
        self.obj.conflate(self.current_bu_osm)

    def _test_zoning(self):
        print 'start', datetime.now()
        d = time.time()
        #urban_zoning = layer.ZoningLayer(baseName='urbanzoning')
        rustic_zoning = layer.ZoningLayer(baseName='rusticzoning')
        #urban_zoning.append(self.zoning_gml, level='M')
        rustic_zoning.append(self.zoning_gml, level='P')
        #print 'urban', urban_zoning.featureCount()
        print 'rustic', rustic_zoning.featureCount()
        index = QgsSpatialIndex(self.building_gml.getFeatures())
        #indexp = QgsSpatialIndex(self.part_gml.getFeatures())
        #indexo = QgsSpatialIndex(self.other_gml.getFeatures())
        print 'index', 1000 * (time.time() - d)
        d = time.time()
        i = 0
        processed = set()
        for zone in rustic_zoning.getFeatures():
            i += 1
            refs = set()
            task = layer.ConsLayer(baseName=zone['label'])
            task.append_zone(self.building_gml, zone, processed, index)
            print 'zone', 1000 * (time.time() - d), i
            d = time.time()
            for feat in task.getFeatures():
                refs.add(feat['localId'])
            #print 'refs', 1000 * (time.time() - d)
            #d = time.time()
            task.append_task(self.part_gml, refs)
            #task.append_zone(self.part_gml, zone, processed, indexp)
            print 'part', 1000 * (time.time() - d)
            d = time.time()
            task.append_task(self.other_gml, refs)
            #task.append_zone(self.other_gml, zone, processed, indexp)
            print 'other', 1000 * (time.time() - d)
            d = time.time()
            processed = processed.union(refs)
            del task
            print i
            if i > 0: break
        print 'end', datetime.now()


class BaseConsTimer(BaseTimer):

    def __init__(self):
        self.mun = '38900'
        building_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.building.gml'.format(self.mun)
        buildingpart_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.buildingpart.gml'.format(self.mun)
        other_fn = BASEPATH + '{0}/A.ES.SDGC.BU.{0}.otherconstruction.gml'.format(self.mun)
        self.building_gml = QgsVectorLayer(building_fn, 'building', 'ogr')
        self.part_gml = QgsVectorLayer(buildingpart_fn, 'buildingpart', 'ogr')
        self.other_gml = QgsVectorLayer(other_fn, 'otherconstruction', 'ogr')
        print self.building_gml.featureCount(), self.part_gml.featureCount(), \
            self.other_gml.featureCount()

    def create_shp(self, name):
        QgsVectorFileWriter(name, 'UTF-8', QgsFields(), QGis.WKBMultiPolygon, 
            self.building_gml.crs(), 'ESRI Shapefile')

    def create_bd(self, name):
        QgsVectorFileWriter(name, 'UTF-8', QgsFields(), QGis.WKBMultiPolygon, 
            self.building_gml.crs(), 'SQLite', datasourceOptions=["SPATIALITE=YES",])


class TimerFixMemUsage(BaseConsTimer):

    def __init__(self):
        super(TimerFixMemUsage, self).__init__()
        self.create_shp('building.shp')
        self.create_shp('building2.shp')
        self.obj = layer.ConsLayer('building.shp', 'building', 'ogr')
        self.obj2 = layer.ConsLayer('building2.shp', 'building', 'ogr')
        assert self.obj.isValid()
        assert self.obj2.isValid()
        
    def _test_append1(self):
        layer = self.building_gml
        self.obj.setCrs(layer.crs())
        to_add = []
        progress = ProgressBar(layer.featureCount())
        for feature in layer.getFeatures():
            to_add.append(self.obj.copy_feature(feature))
            progress.update()
        if to_add:
            self.obj.writer.addFeatures(to_add)
        assert self.obj.featureCount() == self.building_gml.featureCount()
    
    def test_append2(self):
        """As fast as append but with much less memory usage"""
        layer = self.building_gml
        self.obj2.setCrs(layer.crs())
        chunk_size = 512
        to_add = []
        progress = ProgressBar(layer.featureCount())
        for feature in layer.getFeatures():
            to_add.append(self.obj2.copy_feature(feature))
            progress.update()
            if len(to_add) == chunk_size:
                self.obj2.writer.addFeatures(to_add)
                to_add = []
        if len(to_add) > 0:
            self.obj2.writer.addFeatures(to_add)
        assert self.obj2.featureCount() == self.building_gml.featureCount()

    def _test_reproject1(self):
        target_crs = QgsCoordinateReferenceSystem(4326)
        crs_transform = QgsCoordinateTransform(self.obj2.crs(), target_crs)
        to_add = []
        to_clean = []
        progress = ProgressBar(self.obj2.featureCount())
        for feature in self.obj2.getFeatures():
            geom = feature.geometry()
            geom.transform(crs_transform)
            out_feat = QgsFeature()
            out_feat.setGeometry(geom)
            out_feat.setAttributes(feature.attributes())
            to_add.append(out_feat)
            to_clean.append(feature.id())
            progress.update()
        self.obj2.deleteFeatures(to_clean)
        self.obj2.writer.addFeatures(to_add)
        self.obj2.setCrs(target_crs)
        self.obj2.updateExtents()

    def _test_reproject2(self):
        """Less memory usage than reproject1 but slower"""
        target_crs = QgsCoordinateReferenceSystem(4326)
        crs_transform = QgsCoordinateTransform(self.obj2.crs(), target_crs)
        chunk_size = 512
        to_add = []
        to_clean = []
        progress = ProgressBar(self.obj2.featureCount())
        for feature in self.obj2.getFeatures():
            geom = feature.geometry()
            geom.transform(crs_transform)
            out_feat = QgsFeature()
            out_feat.setGeometry(geom)
            out_feat.setAttributes(feature.attributes())
            to_add.append(out_feat)
            to_clean.append(feature.id())
            progress.update()
            if len(to_add) == chunk_size:
                self.obj2.deleteFeatures(to_clean)
                self.obj2.writer.addFeatures(to_add)
                to_add = []
                to_clean = []
        if len(to_add) > 0:
            self.obj2.deleteFeatures(to_clean)
            self.obj2.writer.addFeatures(to_add)
        self.obj2.setCrs(target_crs)
        self.obj2.updateExtents()

    def test_reproject3(self):
        target_crs = QgsCoordinateReferenceSystem(4326)
        crs_transform = QgsCoordinateTransform(self.obj2.crs(), target_crs)
        chunk_size = 512
        to_change = {}
        progress = ProgressBar(self.obj2.featureCount())
        for feature in self.obj2.getFeatures():
            geom = QgsGeometry(feature.geometry())
            geom.transform(crs_transform)
            to_change[feature.id()] = geom
            progress.update()
            if len(to_change) == chunk_size:
                self.obj2.writer.changeGeometryValues(to_change)
                to_change = {}
        if len(to_change) > 0:
            self.obj2.writer.changeGeometryValues(to_change)
        self.obj2.setCrs(target_crs)
        self.obj2.updateExtents()

    def __del__(self):
        QgsVectorFileWriter.deleteShapeFile('building.shp')
        QgsVectorFileWriter.deleteShapeFile('building2.shp')


class TimerFixMemUsageAd(BaseTimer):

    def __init__(self):
        mun = '38900'
        super(TimerFixMemUsageAd, self).__init__()
        address_fn = BASEPATH + '{0}/A.ES.SDGC.AD.{0}.gml'.format(mun)
        self.address_gml = QgsVectorLayer(address_fn, 'address', 'ogr')
        self.tn_gml = QgsVectorLayer(address_fn + '|layername=thoroughfarename', 'tn', 'ogr')
        self.pd_gml = QgsVectorLayer(address_fn + '|layername=postaldescriptor', 'pd', 'ogr')
        assert self.address_gml.isValid()
        QgsVectorFileWriter('address.shp', 'UTF-8', QgsFields(), QGis.WKBPoint, 
            self.address_gml.crs(), 'ESRI Shapefile')
        self.obj = layer.AddressLayer('address.shp', 'address', 'ogr')
        print self.address_gml.featureCount()

    @staticmethod
    def join_field(dest_layer, source_layer, target_field_name, join_field_name,
            field_names_subset, prefix = ""):
        fields = []
        target_attrs = [f.name() for f in dest_layer.pendingFields()]
        for attr in field_names_subset:
            field = source_layer.pendingFields().field(attr)
            field.setName(prefix + attr)
            if field.name() not in target_attrs:
                if field.length() > 254:
                    field.setLength(254)
                fields.append(field)
        dest_layer.writer.addAttributes(fields)
        dest_layer.updateFields()
        source_values = {}
        for feature in source_layer.getFeatures():
            source_values[feature[join_field_name]] = \
                    {attr: feature[attr] for attr in field_names_subset}
        to_change = {}
        progress = ProgressBar(dest_layer.featureCount())
        for feature in dest_layer.getFeatures():
            attrs = {}
            for attr in field_names_subset:
                fieldId = feature.fieldNameIndex(prefix + attr)
                value = None
                if feature[target_field_name] in source_values:
                    value = source_values[feature[target_field_name]][attr]
                attrs[fieldId] = value
            to_change[feature.id()] = attrs
            progress.update()
        if to_change:
            dest_layer.writer.changeAttributeValues(to_change)

    @staticmethod
    def join_field2(dest_layer, source_layer, target_field_name, join_field_name,
            field_names_subset, prefix = ""):
        fields = []
        target_attrs = [f.name() for f in dest_layer.pendingFields()]
        for attr in field_names_subset:
            field = source_layer.pendingFields().field(attr)
            field.setName(prefix + attr)
            if field.name() not in target_attrs:
                if field.length() > 254:
                    field.setLength(254)
                fields.append(field)
        dest_layer.writer.addAttributes(fields)
        dest_layer.updateFields()
        source_values = {}
        for feature in source_layer.getFeatures():
            source_values[feature[join_field_name]] = \
                    {attr: feature[attr] for attr in field_names_subset}
        chunk_size = 512
        to_change = {}
        progress = ProgressBar(dest_layer.featureCount())
        for feature in dest_layer.getFeatures():
            attrs = {}
            for attr in field_names_subset:
                fieldId = feature.fieldNameIndex(prefix + attr)
                value = None
                if feature[target_field_name] in source_values:
                    value = source_values[feature[target_field_name]][attr]
                attrs[fieldId] = value
            to_change[feature.id()] = attrs
            progress.update()
            if len(to_change) == chunk_size:
                dest_layer.writer.changeAttributeValues(to_change)
                to_change = {}
        if len(to_change) > 0:
            dest_layer.writer.changeAttributeValues(to_change)

    def test_append(self):
        layer = self.address_gml
        self.obj.setCrs(layer.crs())
        chunk_size = 512
        to_add = []
        progress = ProgressBar(layer.featureCount())
        for feature in layer.getFeatures():
            to_add.append(self.obj.copy_feature(feature))
            progress.update()
            if len(to_add) == chunk_size:
                self.obj.writer.addFeatures(to_add)
                to_add = []
        if len(to_add) > 0:
            self.obj.writer.addFeatures(to_add)
        assert self.obj.featureCount() == layer.featureCount()

    def test_join(self):
        self.join_field2(self.obj, self.pd_gml, 'PD_id', 'gml_id', ['postCode'])
        self.join_field2(self.obj, self.tn_gml, 'TN_id', 'gml_id', ['text'], 'TN_')

    def __del__(self):
        QgsVectorFileWriter.deleteShapeFile('address.shp')

class ConsTimer(BaseConsTimer):

    def test_10_remove_outside_parts(self):
        self.obj.remove_outside_parts()
        
    def test_11_explode_multi_parts(self):
        self.obj.explode_multi_parts()

    def test_12_remove_parts_below_ground(self):
        self.obj.remove_parts_below_ground()

    def test_13_merge_duplicates(self):
        self.obj.merge_duplicates()

    def test_14_clean_duplicated_nodes_in_polygons(self):
        self.obj.clean_duplicated_nodes_in_polygons()

    def test_15_add_topological_points(self):
        self.obj.add_topological_points()

    def test_16_merge_building_parts(self):
        self.obj.merge_building_parts()

    def test_17_simplify(self):
        self.obj.simplify()

class TimerMemLayer(ConsTimer):

    def __init__(self):
        super(TimerMemLayer, self).__init__()
        self.obj = layer.ConsLayer()

    def test_01_append_all(self):
        self.obj.append(self.building_gml)
        self.obj.append(self.part_gml)
        self.obj.append(self.other_gml)
        assert self.obj.featureCount() > 0

class TimerBdLayer(ConsTimer):

    def __init__(self):
        super(TimerBdLayer, self).__init__()
        self.create_bd('building.sqlite')
        self.obj = layer.ConsLayer('building.sqlite', 'building', 'ogr')
        assert self.obj.isValid()

    def test_01_append_all(self):
        self.obj.append(self.building_gml)
        assert self.obj.featureCount() == self.building_gml.featureCount()
        self.obj.append(self.part_gml)
        assert self.obj.featureCount() == self.building_gml.featureCount() + \
            self.part_gml.featureCount()
        self.obj.append(self.other_gml)

    def __del__(self):
        os.remove('building.sqlite')

class TimerShpLayer(ConsTimer):
    """Similar to MEM faster than BD"""

    def __init__(self):
        super(TimerShpLayer, self).__init__()
        self.create_shp('building.shp')
        self.obj = layer.ConsLayer('building.shp', 'building', 'ogr')
        assert self.obj.isValid()
        
    def _test_01_export_building(self):
        """2x faster than test_append"""
        src_fields = self.building_gml.pendingFields()
        dst_fields = []
        dst_fields.append(src_fields.fieldNameIndex('localId'))
        dst_fields.append(src_fields.fieldNameIndex('conditionOfConstruction'))
        dst_fields.append(src_fields.fieldNameIndex('currentUse'))
        dst_fields.append(src_fields.fieldNameIndex('numberOfBuildingUnits'))
        dst_fields.append(src_fields.fieldNameIndex('numberOfDwellings'))
        dst_fields.append(src_fields.fieldNameIndex('documentLink'))
        QgsVectorFileWriter.writeAsVectorFormat(self.building_gml, 'building.shp', "utf-8",
                self.building_gml.crs(), 'ESRI Shapefile', attributes=dst_fields)
        self.building_shp = QgsVectorLayer('temp.shp', 'building', 'ogr')
        QgsVectorFileWriter.deleteShapeFile('temp.shp')

    def test_02_append_building(self):
        self.obj.append(self.building_gml)
        assert self.obj.featureCount() > 0
    
    def test_03_append_part_other(self):
        self.obj.append(self.part_gml)
        self.obj.append(self.other_gml)
    
    def __del__(self):
        QgsVectorFileWriter.deleteShapeFile('building.shp')

class BaseBuildingTimer(BaseConsTimer):

    def __init__(self):
        print 'start', datetime.now()
        d = time.time()
        super(BaseBuildingTimer, self).__init__()
        self.create_shp('building.shp')
        self.obj = layer.ConsLayer('building.shp', 'building', 'ogr')
        #self.obj = layer.ConsLayer()
        self.obj.append(self.building_gml)
        print 'building', 1000 * (time.time() - d), self.obj.featureCount()
        d = time.time()
        self.obj.append(self.part_gml)
        print 'parts', 1000 * (time.time() - d), self.obj.featureCount()
        d = time.time()
        self.obj.append(self.other_gml)
        print 'others', 1000 * (time.time() - d), self.obj.featureCount()

    def __del__(self):
        QgsVectorFileWriter.deleteShapeFile('building.shp')

class TimerVertices(BaseBuildingTimer):

    def __init__(self):
        super(TimerVertices, self).__init__()
        d = time.time()
        self.obj_shp = self.obj.get_vertices()
        print 'vertices_shp', 1000 * (time.time() - d), self.obj_shp.featureCount()
        d = time.time()
        self.obj = layer.BaseLayer('Point', 'vertices', 'memory')
        self.obj.append(self.obj_shp)
        print 'vertices_mem', 1000 * (time.time() - d), self.obj.featureCount()

    def __del__(self):
        self.obj_shp.delete_shp()

    def _test_duplicates_mem(self):
        dup_thr = 0.012
        duplicates = defaultdict(list)
        index = self.obj.get_index()
        vertices_by_fid = {feat.id(): feat for feat in self.obj.getFeatures()}
        for vertex in self.obj.getFeatures():
            point = layer.Point(vertex.geometry().asPoint())
            area_of_candidates = point.boundingBox(dup_thr)
            fids = index.intersects(area_of_candidates)
            fids.remove(vertex.id())
            for fid in fids:
                dup = vertices_by_fid[fid].geometry().asPoint()
                dist = point.sqrDist(dup)
                if dist < dup_thr**2:
                    duplicates[point].append(dup)
        print("duplicados %d" % len(duplicates))

    def _test_duplicates_shp1(self):
        """3x slower than test_duplicates_mem, 3x less memory"""
        dup_thr = 0.012
        duplicates = defaultdict(list)
        index = self.obj_shp.get_index()
        request = QgsFeatureRequest()
        for vertex in self.obj_shp.getFeatures():
            point = layer.Point(vertex.geometry().asPoint())
            area_of_candidates = point.boundingBox(dup_thr)
            fids = index.intersects(area_of_candidates)
            fids.remove(vertex.id())
            if fids:
                request.setFilterFids(fids)
                for v in self.obj_shp.getFeatures(request):
                    dup = v.geometry().asPoint()
                    dist = point.sqrDist(dup)
                    if dist < dup_thr**2:
                        duplicates[point].append(dup)
        print("duplicados %d" % len(duplicates))

    def test_duplicates_shp2(self):
        """1.1x slower than test_duplicates_mem, 2x less memory"""
        dup_thr = 0.012
        duplicates = defaultdict(list)
        index = self.obj_shp.get_index()
        vertices_by_fid = {feat.id(): feat.geometry().asPoint() for feat in self.obj_shp.getFeatures()}
        for vertex in self.obj_shp.getFeatures():
            point = layer.Point(vertex.geometry().asPoint())
            area_of_candidates = point.boundingBox(dup_thr)
            fids = index.intersects(area_of_candidates)
            fids.remove(vertex.id())
            for fid in fids:
                dup = vertices_by_fid[fid]
                dist = point.sqrDist(dup)
                if dist < dup_thr**2:
                    duplicates[point].append(dup)
        print("duplicados %d" % len(duplicates))

class AppendZoneTimer(BaseBuildingTimer):

    def __init__(self):
        super(AppendZoneTimer, self).__init__()
        d = time.time()
        self.index = QgsSpatialIndex(self.obj.getFeatures())
        print 'index', 1000 * (time.time() - d)
        d = time.time()
        zoning_fn = BASEPATH + '{0}/A.ES.SDGC.CP.{0}.cadastralzoning.gml'.format(self.mun)
        zoning_gml = QgsVectorLayer(zoning_fn, 'zoning', 'ogr')
        self.urban_zoning = layer.ZoningLayer(baseName='urbanzoning')
        self.rustic_zoning = layer.ZoningLayer(baseName='rusticzoning')
        self.urban_zoning.append(zoning_gml, level='M')
        print 'urban_zoning', 1000 * (time.time() - d), self.urban_zoning.featureCount()
        d = time.time()
        self.rustic_zoning.append(zoning_gml, level='P')
        print 'rustic_zoning', 1000 * (time.time() - d), self.rustic_zoning.featureCount()

    def append_zone(self, dest, source, zone, processed, index):
        query = lambda f, kwargs: not '_' in f['localId'] and f.id() in fids and \
            f['localId'] not in kwargs['excluding'] and layer.is_inside(f, kwargs['zone'])
        fids = index.intersects(zone.geometry().boundingBox())
        super(layer.ConsLayer, dest).append(source, query=query, zone=zone, fids=fids, 
            excluding=processed)

    def append_task(self, dest, source, task):
        query = lambda f, kwargs: '_' in f['localId'] and \
            f['localId'].split('_')[0] in kwargs['including']
        super(layer.ConsLayer, dest).append(source, query=query, including=task)

    def append_zone2(self, dest, source, zone, processed, index, parts=False):
        dest.setCrs(source.crs())
        fids = index.intersects(zone.geometry().boundingBox())
        request = QgsFeatureRequest().setFilterFids(fids)
        to_add = []
        features = []
        refs = set()
        total = 0
        for feat in source.getFeatures(request):
            if not feat['localId'] in processed:
                if not '_' in feat['localId'] and layer.is_inside(feat, zone):
                    to_add.append(dest.copy_feature(feat))
                    refs.add(feat['localId'])
                    total += 1
                else:
                    features.append(feat)
            if len(to_add) > layer.BUFFER_SIZE:
                dest.writer.addFeatures(to_add)
                to_add = []
        if parts:
            for feat in features:
                if '_' in feat['localId'] and feat['localId'].split('_')[0] in refs:
                    to_add.append(dest.copy_feature(feat))
                    total += 1
                if len(to_add) > layer.BUFFER_SIZE:
                    dest.writer.addFeatures(to_add)
                    to_add = []
        if len(to_add) > 0:
             dest.writer.addFeatures(to_add)
        return refs

    def test_append_zone_0(self):
        rprocessed = set()
        rindex = self.index
        rzone = self.rustic_zoning.getFeatures().next()
        task = layer.ConsLayer(baseName=rzone['label'])
        self.append_zone(task, self.building_gml, rzone, rprocessed, rindex)
        refs = set()
        for feat in task.getFeatures():
            refs.add(feat['localId'])
        print 'refs', len(refs)
        self.append_task(task, self.part_gml, refs)
        print task.featureCount()
        self.append_task(task, self.other_gml, refs)
        print task.featureCount()

    def test_append_zone_1(self):
        rprocessed = set()
        rindex = self.index
        rzone = self.rustic_zoning.getFeatures().next()
        task = layer.ConsLayer(baseName=rzone['label'])
        task.rename = {}
        self.append_zone(task, self.obj, rzone, rprocessed, rindex)
        refs = set()
        for feat in task.getFeatures():
            refs.add(feat['localId'])
        print 'refs', len(refs)
        self.append_task(task, self.obj, refs)
        print task.featureCount()

    def test_append_zone2(self):
        rprocessed = set()
        rindex = self.index
        rzone = self.rustic_zoning.getFeatures().next()
        task = layer.ConsLayer(baseName=rzone['label'])
        task.rename = {}
        refs = self.append_zone2(task, self.obj, rzone, rprocessed, rindex)
        print 'refs', len(refs)
        self.append_task(task, self.obj, refs)
        print task.featureCount()

    def test_append_zone3(self):
        rprocessed = set()
        rindex = self.index
        rzone = self.rustic_zoning.getFeatures().next()
        task = layer.ConsLayer(baseName=rzone['label'])
        task.rename = {}
        refs = self.append_zone2(task, self.obj, rzone, rprocessed, rindex, True)
        print 'refs', len(refs)
        print task.featureCount()

class TimerOsm(BaseTimer):

    def set_up(self):
        mun = '38012'
        osm_path = BASEPATH + mun + '/current_building.osm'
        fo = open(osm_path, 'r')
        self.obj = osmxml.deserialize(fo)
        self.to_clean = []
        for i, el in enumerate(self.obj.elements):
            if i % 10 == 0:
                self.to_clean.append(el)

    def test_remove(self):
        for el in self.to_clean:
            if el in self.obj.elements:
                self.obj.remove(el)

class TimerZoningLayer(BaseTimer):

    def __init__(self):
        mun = '28900'
        zoning_fn = BASEPATH + '{0}/A.ES.SDGC.CP.{0}.cadastralzoning.gml'.format(mun)
        self.zoning_gml = QgsVectorLayer(zoning_fn, 'zoning', 'ogr')
        layer.ZoningLayer.create_shp('urban_zoning.shp', self.zoning_gml.crs())
        self.obj = layer.ZoningLayer()

    def _test_append_urban(self):
        fn = 'urban_zoning.shp'
        layer.ZoningLayer.create_shp(fn, self.zoning_gml.crs())
        urban = layer.ZoningLayer(fn, 'zoning', 'ogr')
        urban.append(self.zoning_gml, 'M')
        QgsVectorFileWriter.deleteShapeFile(fn)

    def _test_append_rustic(self):
        fn = 'rustic_zoning.shp'
        layer.ZoningLayer.create_shp(fn, self.zoning_gml.crs())
        rustic = layer.ZoningLayer(fn, 'zoning', 'ogr')
        rustic.append(self.zoning_gml, 'M')
        QgsVectorFileWriter.deleteShapeFile(fn)
        
    def _test_copy(self):
        fn1 = 'urban_zoning.shp'
        fn2 = 'rustic_zoning.shp'
        fields = self.zoning_gml.pendingFields()
        attrs = [fields.indexFromName('levelName'), fields.indexFromName('label')]
        QgsVectorFileWriter.writeAsVectorFormat(self.zoning_gml, fn1, 'utf-8', 
            self.zoning_gml.crs(), 'ESRI Shapefile', attributes=attrs,
            forceMulti=True, overrideGeometryType=QgsWKBTypes.Polygon)
        layer1 = layer.ZoningLayer(fn1, 'urban_zoning', 'ogr')
        layer1.selectByExpression("levelName like '%POLIGONO%'")
        QgsVectorFileWriter.writeAsVectorFormat(layer1, fn2, 'utf-8', 
            layer1.crs(), 'ESRI Shapefile', onlySelected=True)
        layer2 = layer.ZoningLayer(fn2, 'rustic_zoning', 'ogr')
        layer1.writer.deleteFeatures(layer1.selectedFeaturesIds())
        QgsVectorFileWriter.deleteShapeFile(fn1)
        QgsVectorFileWriter.deleteShapeFile(fn2)
    
    def _test_mem(self):
        layer1 = layer.ZoningLayer()
        layer1.append(self.zoning_gml, 'M')
        layer2 = layer.ZoningLayer()
        layer2.append(self.zoning_gml, 'P')
    
    def test_multi(self):
        """Some multisurface features in zoning gml are wrongly converted to polygons"""
        fn = 'urban_zoning.shp'
        layer.ZoningLayer.create_shp(fn, self.zoning_gml.crs())
        urban = layer.ZoningLayer(fn, 'zoning', 'ogr')
        fixture = QgsVectorLayer('test/zoning.gml', 'zoning', 'ogr')
        exp = QgsExpression("inspireId_localId = '69297CS5262N'")
        request = QgsFeatureRequest(exp)
        f = fixture.getFeatures(request).next()
        g = f.geometry()
        print 'multipolygon', [[[len(r)] for r in p] for p in g.asMultiPolygon()]
        urban.writer.addFeatures([f])
        f = urban.getFeatures().next()
        g = f.geometry()
        print 'to wrong polygon', [len(r) for r in g.asPolygon()]
        QgsVectorFileWriter.deleteShapeFile(fn)


if __name__ == '__main__':
    #TimerBaseLayer().run()
    #TimerPolygonLayer().run()
    #TimerAddressLayer2().run()
    #TimerOsm().run()
    """
    TimerConsLayer().run()
    d = time.time()
    TimerMemLayer().run()
    print 'MEM', 1000 * (time.time() - d)
    d = time.time()
    #TimerBdLayer().run()
    #print 'BD', 1000 * (time.time() - d)
    #d = time.time()
    TimerShpLayer().run()
    print 'SHP', 1000 * (time.time() - d)
    d = time.time()
    TimerFixMemUsageAd().run()
    TimerZoningLayer().run()
    TimerVertices().run()
    """
    AppendZoneTimer().run()
