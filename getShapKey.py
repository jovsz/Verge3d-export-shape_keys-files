
import bpy
from os.path import join


o = bpy.context.active_object

exportPath = "C:\exportShape"

print(o.data.shape_keys.key_blocks[2].value)

for skblock in o.data.shape_keys.key_blocks[1:]:
    print(skblock.name)
    print(skblock.value)

#for skblock in o.data.shape_keys.key_blocks[1:]:
#    skblock.value = 1.0


#    objFileName = skblock.name + ".gltf"
#    objPath = join( exportPath, objFileName )
#    bpy.ops.export_scene.obj( filepath = objPath, use_selection = True, global_scale = 1 )

#    skblock.value = 0