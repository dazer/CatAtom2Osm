import unittest
import random

import main
import osm
import osmxml
from osmxml import etree


class OsmxmlTest(unittest.TestCase):

    def test_serialize(self):
        data = osm.Osm()
        n = data.Node(4,0)
        n.tags['entrance'] = 'yes'
        n.tags['addr:street'] = 'Calle la X'
        n.tags['addr:housenumber'] = '7'
        w = data.Way([(12,0), (14,0), (14,2), (12,2), (12,0)])
        w.tags['leisure'] = 'swiming_pool'
        r = data.MultiPolygon([[
            [(0,0), (10,0), (10,6), (0,6), (0,0)], 
            [(8,1), (9,1), (9,2), (8,2), (8,1)]
        ]])
        r.tags['building'] = 'residential'
        result = osmxml.serialize(data)
        root = etree.fromstring(result)
        self.assertEquals(root.xpath('count(//way)'), 3)
        self.assertEquals(root.xpath('count(//relation)'), 1)
        for (xmlnode, osmnode) in zip(root.findall('node'), data.nodes):
            self.assertEquals(float(xmlnode.get('lon')), osmnode.x) 
            self.assertEquals(float(xmlnode.get('lat')), osmnode.y)
        for (xmltag, osmtag) in zip(root.findall('node/tag'), n.tags.items()):
            self.assertEquals(xmltag.get('k'), osmtag[0])
            self.assertEquals(xmltag.get('v'), osmtag[1])
        for (xmlway, osmway) in zip(root.findall('way'), data.ways):
            for (xmlnd, osmnd) in zip(xmlway.findall('nd'), osmway.nodes):
                self.assertEquals(int(xmlnd.get('ref')), osmnd.id)
        for (xmltag, osmtag) in zip(root.findall('way/tag'), w.tags.items()):
            self.assertEquals(xmltag.get('k'), osmtag[0])
            self.assertEquals(xmltag.get('v'), osmtag[1])
        for (i, (xmlm, osmm)) in enumerate(zip(root.findall('relation/member'), r.members)):
            self.assertEquals(int(xmlm.get('ref')), osmm.ref)
            self.assertEquals(xmlm.get('role'), 'outer' if i == 0 else 'inner')
        for (xmltag, osmtag) in zip(root.findall('relation/tag'), r.tags.items()):
            self.assertEquals(xmltag.get('k'), osmtag[0])
            self.assertEquals(xmltag.get('v'), osmtag[1])
        self.assertEquals(root.find('note'), None)
        self.assertEquals(root.find('meta'), None)
        data.note = 'foobar'
        data.meta = {'foo': 'bar'}
        data.tags['type'] = 'import'
        result = osmxml.serialize(data)
        root = etree.fromstring(result)
        for (xmltag, osmtag) in zip(root.findall('changeset/tag'), data.tags.items()):
            self.assertEquals(xmltag.get('k'), osmtag[0])
            self.assertEquals(xmltag.get('v'), osmtag[1])
        self.assertEquals(root.find('note').text, 'foobar')
        self.assertEquals(root.find('meta').get('foo'), 'bar')

    def test_deserialize(self):
        attrs = dict(upload='1', version='2', generator='3')
        root = etree.Element('osm', attrs)
        nodexml = etree.Element('node', dict(id='-1', lon='4', lat='0'))
        nodexml.append(etree.Element('tag', dict(k='entrance', v='yes')))
        nodexml.append(etree.Element('tag', dict(k='addr:street', v='Calle la X')))
        nodexml.append(etree.Element('tag', dict(k='addr:housenumber', v='7')))
        root.append(nodexml)
        wayxml = etree.Element('way', dict(id='-100'))
        for (i, node) in enumerate([(12,0), (14,0), (14,2), (12,2), (12,0)]):
            nodexml = etree.Element('node', dict(id=str(-i-10), lon=str(node[0]), lat=str(node[1])))
            root.append(nodexml)
            wayxml.append(etree.Element('nd', dict(ref=str(nodexml.get('id')))))
        wayxml.append(etree.Element('tag', dict(k='leisure', v='swiming_pool')))
        root.append(wayxml)
        wayxml = etree.Element('way', dict(id='-101'))
        for (i, node) in enumerate([(0,0), (10,0), (10,6), (0,6), (0,0)]):
            nodexml = etree.Element('node', dict(id=str(-i-20), lon=str(node[0]), lat=str(node[1])))
            root.append(nodexml)
            wayxml.append(etree.Element('nd', dict(ref=str(nodexml.get('id')))))
        root.append(wayxml)
        wayxml = etree.Element('way', dict(id='-102'))
        for (i, node) in enumerate([(8,1), (9,1), (9,2), (8,2), (8,1)]):
            nodexml = etree.Element('node', dict(id=str(-i-30), lon=str(node[0]), lat=str(node[1])))
            root.append(nodexml)
            wayxml.append(etree.Element('nd', dict(ref=str(nodexml.get('id')))))
        root.append(wayxml)
        relxml = etree.Element('relation', dict(id='-200'))
        relxml.append(etree.Element('member', dict(type='way', ref='-101', role='outter')))
        relxml.append(etree.Element('member', dict(type='way', ref='-102', role='inner')))
        relxml.append(etree.Element('tag', dict(k='building', v='residential')))
        root.append(relxml)
        result = osmxml.deserialize(root)
        self.assertEquals(result.upload, '1')
        self.assertEquals(result.version, '2')
        self.assertEquals(result.generator, '3')
        self.assertEquals(len(result.nodes), 16)
        self.assertEquals(len(result.ways), 3)
        self.assertEquals(len(result.relations), 1)
        for osmnode in result.nodes:
            xmlnode = root.find("node[@id='%d']" % osmnode.id)
            self.assertEquals(int(xmlnode.get('id')), osmnode.id)
            self.assertEquals(float(xmlnode.get('lon')), osmnode.x) 
            self.assertEquals(float(xmlnode.get('lat')), osmnode.y)
        tags = {t.get('k'): t.get('v') for t in root.findall("node[@id='-1']/tag")}
        self.assertEquals(tags['entrance'], 'yes')
        self.assertEquals(tags['addr:street'], 'Calle la X')
        self.assertEquals(tags['addr:housenumber'], '7')
        for osmway in result.ways:
            xmlway = root.find("way[@id='%d']" % osmway.id)
            self.assertEquals(int(xmlway.get('id')), osmway.id)
            for nd in xmlway.findall('nd'):
                self.assertIn(nd.get('ref'), [str(w.id) for w in osmway.nodes])
        tags = {t.get('k'): t.get('v') for t in root.findall("way[@id='-100']/tag")}
        self.assertEquals(tags, dict(leisure='swiming_pool'))
        osmrel = result.relations[0]
        xmlrel = root.find("relation[@id='%d']" % osmrel.id)
        self.assertEquals(int(xmlrel.get('id')), osmrel.id)
        roles = []
        for m in xmlrel.findall('member'):
            self.assertIn(m.get('ref'), [str(x.ref) for x in osmrel.members])
            self.assertEquals(m.get('type'), 'way')
            roles.append(m.get('role'))
        self.assertEquals(roles, ['outter', 'inner'])
        tags = {t.get('k'): t.get('v') for t in root.findall("relation[@id='-200']/tag")}
        self.assertEquals(tags, dict(building='residential'))
        nxml = etree.Element('note')
        nxml.text = 'foobar'
        root.append(nxml)
        mxml = etree.Element('meta')
        mxml.set('foo', 'bar')
        root.append(mxml)
        csxml = etree.Element('changeset')
        csxml.append(etree.Element('tag', dict(k='type', v='import')))
        root.append(csxml)
        result = osmxml.deserialize(root)
        self.assertEquals(result.note, 'foobar')
        self.assertEquals(result.meta, dict(foo='bar'))
        self.assertEquals(result.tags, dict(type='import'))
        root = etree.Element('osm')
        nodexml = etree.Element('node', dict(id='-50', lon='0', lat='4'))
        root.append(nodexml)
        result = osmxml.deserialize(root, result)
        self.assertEquals(len(result.nodes), 17)

