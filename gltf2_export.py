# Copyright (c) 2017 The Khronos Group Inc.
# Modifications Copyright (c) 2017-2019 Soft8Soft LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
import json
import struct
import os
import requests
from pluginUtils.log import *
from pluginUtils.manager import AppManagerConn
import pprint

from .gltf2_filter import *
from .gltf2_generate import *

url = 'http://localhost:8000/api/v1/minio/fileblender/'
pp = pprint.PrettyPrinter(width=41, compact=True)

def prepare(exportSettings):
    """
    Stores current state of Blender and prepares for export, depending on the current export settings.
    """
    if bpy.context.active_object is not None and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    filterApply(exportSettings)

    exportSettings['original_frame'] = bpy.context.scene.frame_current

    exportSettings['use_no_color'] = []

    exportSettings['joint_cache'] = {}

    if exportSettings['animations']:
        bpy.context.scene.frame_set(0)

def finish(exportSettings):
    """
    Brings back Blender into its original state before export and cleans up temporary objects.
    """
    if exportSettings['temporary_meshes'] is not None:
        for temporary_mesh in exportSettings['temporary_meshes']:
            bpy.data.meshes.remove(temporary_mesh)

    if exportSettings['temporary_materials'] is not None:
        for temporary_mat in exportSettings['temporary_materials']:
            bpy.data.materials.remove(temporary_mat)

    for bl_image in exportSettings['filtered_images']:
        del bl_image['compression_error_status']

    del exportSettings['uri_cache']['uri'][:]
    del exportSettings['uri_cache']['bl_datablocks'][:]

    # HACK: fix user count for materials, which can be 0 in case of copying objects
    # for bpy.data.meshes.new_from_object operation
    for obj in bpy.data.objects:
        if obj.data is not None and hasattr(obj.data, 'materials'):
            mats = obj.data.materials
            for i in range(len(mats)):
                mats[i] = mats[i]

    bpy.context.scene.frame_set(exportSettings['original_frame'])

def compressLZMA(path, settings):

    if settings['sneak_peek']:
        return

    if not settings['lzma_enabled']:
        return

    AppManagerConn.compressLZMA(path)




def save(operator, context, exportSettings):
    """
    Starts the glTF 2.0 export and saves to content either to a .gltf or .glb file.
    """

    printLog('INFO', 'Starting glTF 2.50 export')
    bpy.context.window_manager.progress_begin(0, 100)
    bpy.context.window_manager.progress_update(0)


    prepare(exportSettings)


    glTF = {}

    generateGLTF(operator, context, exportSettings, glTF)

    cleanupDataKeys(glTF)

    indent = None
    separators = separators=(',', ':')

    jsonStrip = exportSettings['strip'] and not exportSettings['sneak_peek']

    if exportSettings['format'] == 'ASCII' and not jsonStrip:
        indent = 4
        separators = separators=(', ', ' : ')

    glTF_encoded = json.dumps(glTF, indent=indent, separators=separators,
            sort_keys=True, ensure_ascii=False)


    if exportSettings['format'] == 'ASCII':
        file = open(exportSettings['filepath'], 'w', encoding='utf8', newline='\n')
        file.write(glTF_encoded)
        file.write('\n')
        file.close()

        binary = exportSettings['binary']
        if len(binary) > 0:
            file = open(exportSettings['filedirectory'] + exportSettings['binaryfilename'], 'wb')
            file.write(binary)
            file.close()

        compressLZMA(exportSettings['filepath'], exportSettings)

        bin_path = exportSettings['filedirectory'] + exportSettings['binaryfilename']
        if os.path.isfile(bin_path):
            compressLZMA(bin_path, exportSettings)

    else:
        file = open(exportSettings['filepath'], 'wb')

        glTF_data = glTF_encoded.encode()
        binary = exportSettings['binary']

        length_gtlf = len(glTF_data)
        spaces_gltf = (4 - (length_gtlf & 3)) & 3
        length_gtlf += spaces_gltf

        length_bin = len(binary)
        zeros_bin = (4 - (length_bin & 3)) & 3
        length_bin += zeros_bin

        length = 12 + 8 + length_gtlf
        if length_bin > 0:
            length += 8 + length_bin

        # Header (Version 2)
        file.write('glTF'.encode())
        file.write(struct.pack('I', 2))
        file.write(struct.pack('I', length))

        # Chunk 0 (JSON)
        file.write(struct.pack('I', length_gtlf))
        file.write('JSON'.encode())
        file.write(glTF_data)
        for i in range(0, spaces_gltf):
            file.write(' '.encode())

        # Chunk 1 (BIN)
        if length_bin > 0:
            file.write(struct.pack('I', length_bin))
            file.write('BIN\0'.encode())
            file.write(binary)
            for i in range(0, zeros_bin):
                file.write('\0'.encode())

        file.close()

        compressLZMA(exportSettings['filepath'], exportSettings)
    try:
        def getShapeKeys():
            o = bpy.context.collection
            detailObj = {}
            list = []

            for obj in o.all_objects:
                if hasattr(obj.data, 'shape_keys'):
                    print('tiene atributo shape')
                    if hasattr(obj.data.shape_keys, 'key_blocks'):
                        print('tiene atributo key_blocks')
                        detailObj['name'] = obj.name
                        print(obj.name, obj.data.shape_keys.key_blocks)
                        for skblock in obj.data.shape_keys.key_blocks[1:]:
                            list.append({skblock.name: {'value': skblock.value, 'min': skblock.slider_min,'max': skblock.slider_max}})
            detailObj['shape_keys'] = list
            detailObj['type'] = bpy.context.scene.manage_props.component
            detailObj['user'] = bpy.context.scene.manage_props.user
            detailObj['password'] = bpy.context.scene.manage_props.password
            print(detailObj)
            return detailObj





        shapekeys = getShapeKeys()
        print(exportSettings['filepath'])
        binPath = exportSettings['filepath'].split('.')[0] + '.bin'

        src_glft = open(exportSettings['filepath'], 'rb')
        src_bin = open(binPath, 'rb')
        #
        #
        x = requests.post(url,data = shapekeys, files = [('files', src_glft),('files', src_bin)] )

        print(x)
        printLog('INFO', 'Informacion mandada a la api')
    except:
        printLog('INFO', 'Fallo la agrupacion y llamada a la api')
    finish(exportSettings)
    printLog('INFO', 'Finished glTF 2.0 export ')

    bpy.context.window_manager.progress_end()

    return {'FINISHED'}

def cleanupDataKeys(glTF):
    """
    Remove "id" keys used in the exporter to assign entity indices
    """
    for key, val in glTF.items():
        if type(val) == list:
            for entity in val:
                if 'id' in entity:
                    del entity['id']
        elif key == 'extensions' and 'S8S_v3d_lights' in val:
            cleanupDataKeys(val['S8S_v3d_lights'])
        elif key == 'extensions' and 'S8S_v3d_light_probes' in val:
            cleanupDataKeys(val['S8S_v3d_light_probes'])
        elif key == 'extensions' and 'S8S_v3d_clipping_planes' in val:
            cleanupDataKeys(val['S8S_v3d_clipping_planes'])
        elif key == 'extensions' and 'S8S_v3d_curves' in val:
            cleanupDataKeys(val['S8S_v3d_curves'])

