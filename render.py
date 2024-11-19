import bpy
import os
import math
from mathutils import Vector
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, FloatProperty, FloatVectorProperty
from .panels import apply_hdri_rotation, preview_collections

class AddOrApplyHDRI(Operator):
    bl_idname = "epictoolbag.add_or_apply_hdri" 
    bl_label = "Add or Apply HDRI Environment Texture"

    hdri_name: StringProperty()

    def execute(self, context):
        hdri_name = self.hdri_name if self.hdri_name else context.scene.hdri_enum
        pcoll_paths = preview_collections.get("hdri_paths", {})
        hdri_path = pcoll_paths.get(hdri_name)

        if not hdri_path or not os.path.exists(hdri_path):
            self.report({'ERROR'}, f"HDRI file not found: {hdri_path}")
            return {'CANCELLED'}

        world = context.scene.world
        world.use_nodes = True
        nodes = world.node_tree.nodes
        links = world.node_tree.links

        # Check if an environment node already exists and reuse it
        env_tex_node = next((node for node in nodes if node.type == 'TEX_ENVIRONMENT'), None)
        if env_tex_node is None:
            # Clear existing nodes and create necessary ones if no environment node is found
            nodes.clear()
            env_tex_node = nodes.new('ShaderNodeTexEnvironment')
            background_node = nodes.new('ShaderNodeBackground')
            output_node = nodes.new('ShaderNodeOutputWorld')
            links.new(env_tex_node.outputs['Color'], background_node.inputs['Color'])
            links.new(background_node.outputs['Background'], output_node.inputs['Surface'])
        else:
            # If found, just update the image
            background_node = next((node for node in nodes if node.type == 'BACKGROUND'), None)

        # Load and apply the new HDRI image
        env_tex_node.image = bpy.data.images.load(hdri_path, check_existing=True)

        # Add or update the mapping node for rotation control
        mapping_node = next((node for node in nodes if node.type == 'MAPPING'), None)
        if mapping_node is None:
            mapping_node = nodes.new(type='ShaderNodeMapping')
            tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
            links.new(tex_coord_node.outputs['Object'], mapping_node.inputs['Vector'])
            links.new(mapping_node.outputs['Vector'], env_tex_node.inputs['Vector'])

        # Apply HDRI rotation
        apply_hdri_rotation(context)

        self.report({'INFO'}, "HDRI applied.")
        return {'FINISHED'}

class RemoveHDRI(Operator):
    bl_idname = "epictoolbag.remove_hdri"
    bl_label = "Remove HDRI"

    def execute(self, context):
        world = context.scene.world
        if world and world.use_nodes:
            nodes = world.node_tree.nodes
            links = world.node_tree.links

            # Find and remove the TEX_ENVIRONMENT node
            env_tex_node_found = False
            for node in nodes:
                if node.type == 'TEX_ENVIRONMENT':
                    nodes.remove(node)
                    env_tex_node_found = True

            # If a TEX_ENVIRONMENT node was found and removed, reset the world
            if env_tex_node_found:
                # Clear all nodes to revert to the default state
                nodes.clear()
                # Create a new Background and Output node and connect them
                background_node = nodes.new('ShaderNodeBackground')
                output_node = nodes.new('ShaderNodeOutputWorld')
                links.new(background_node.outputs['Background'], output_node.inputs['Surface'])

                # Set the background color to Blender's default dark gray
                background_node.inputs['Color'].default_value = (0.050876, 0.050876, 0.050876, 1) 

                # Ensure the background light intensity is set to default
                background_node.inputs['Strength'].default_value = 1.0

                self.report({'INFO'}, "HDRI removed.")
                return {'FINISHED'}
            else:
                self.report({'INFO'}, "No HDRI to remove.")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "World not used.")
            return {'CANCELLED'}
    
import bpy
import math
import random

class CreateLight(Operator):
    bl_idname = "epictoolbag.create_light"
    bl_label = "Create Light"
    bl_description = "Create a new light in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Definir um nome único para a luz
        light_name = f"Light_{len(bpy.data.lights) + 1}"
        
        # Criar luz padrão (Point light)
        light_data = bpy.data.lights.new(name=light_name, type='POINT')
        light_object = bpy.data.objects.new(name=light_name, object_data=light_data)
        
        # Adicionar à cena
        context.collection.objects.link(light_object)

        # Posicionamento randômico
        if context.scene.objects:
            # Se já existem objetos na cena, posicionar próximo ao centro
            center = context.scene.cursor.location
            offset = random.uniform(3, 7)
            angle = random.uniform(0, 2 * math.pi)
            
            light_object.location = (
                center.x + offset * math.cos(angle),
                center.y + offset * math.sin(angle),
                center.z + random.uniform(2, 5)
            )
        else:
            # Posição padrão se não houver objetos
            light_object.location = (0, 0, 5)

        # Configurações padrão da luz
        light_data.energy = 1000.0
        light_data.color = (1.0, 1.0, 1.0)

        # Selecionar a nova luz
        bpy.ops.object.select_all(action='DESELECT')
        light_object.select_set(True)
        context.view_layer.objects.active = light_object

        return {'FINISHED'}

    @staticmethod
    def log_message(message):
        """Log messages for debugging purposes."""
        print(f"[Epic Toolbag - CreateLight]: {message}")
            
class LightCustomProperties(bpy.types.Panel):
    """Panel for custom light properties"""
    bl_label = "Light Properties"
    bl_idname = "LIGHT_PT_custom_properties"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Epic Toolbag' 
    
    @classmethod
    def poll(cls, context):
        # This function determines if the panel should be shown
        # In this example, it will always return True so the panel is always shown
        return True

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if obj and obj.type == 'LIGHT':
            light = obj.data
            
            layout.prop(light, "type", text="Type")
            layout.prop(light, "energy", text="Energy")
            layout.prop(light, "color", text="Color")
            layout.prop(obj, "location", text="Location")
        else:
            # This block will execute if there is no active object or if the active object is not a light
            layout.label(text="No light selected.", icon='INFO')

class RemoveLight(Operator):
    bl_idname = "epictoolbag.remove_light"
    bl_label = "Remove Light"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'LIGHT'

    def execute(self, context):
        # Store the active light object
        light_object = context.active_object
        
        # Deselect the light object and remove it
        bpy.ops.object.select_all(action='DESELECT')
        light_object.select_set(True)
        bpy.ops.object.delete()

        return {'FINISHED'}

class CreateCamera(Operator):
    bl_idname = "epictoolbag.create_camera"
    bl_label = "Create Camera"
    bl_description = "Create a new camera and activate camera view"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Criar uma nova câmera
        camera_data = bpy.data.cameras.new(name="Camera")
        camera_object = bpy.data.objects.new("Camera", camera_data)
        
        # Adicionar a câmera à cena atual
        context.collection.objects.link(camera_object)

        # Definir como câmera ativa da cena
        context.scene.camera = camera_object

        # Posicionar a câmera com as coordenadas especificadas
        camera_object.location = (0, -10, 6)  # X: 0m, Y: -10m, Z: 6m
        camera_object.rotation_euler = (math.radians(60), 0, 0)  # X: 60°, Y: 0°, Z: 0°

        # Configurações específicas da câmera
        camera_data.shift_x = 0.0  # Shift X
        camera_data.shift_y = 0.0  # Shift Y
        camera_data.lens = 30.0    # Focal Length 30mm

        # Selecionar a nova câmera
        bpy.ops.object.select_all(action='DESELECT')
        camera_object.select_set(True)
        context.view_layer.objects.active = camera_object

        # Alternar para vista da câmera
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
                break

        return {'FINISHED'}

    @staticmethod
    def log_message(message):
        """Log messages for debugging purposes."""
        print(f"[Epic Toolbag - CreateCamera]: {message}")

class RemoveLightCamera(bpy.types.Operator):
    bl_idname = "epictoolbag.remove_light_camera"
    bl_label = "Remove Light/Camera"
    bl_description = "Remove the selected light or camera"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type in {'LIGHT', 'CAMERA'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type in {'LIGHT', 'CAMERA'}:
            bpy.data.objects.remove(obj, do_unlink=True)
            return {'FINISHED'}
        return {'CANCELLED'}

class RemoveCamera(Operator):
    bl_idname = "epictoolbag.remove_camera"
    bl_label = "Remove Camera"
    bl_options = {'REGISTER', 'UNDO'}

    protected_camera_names = ["Default"]

    def execute(self, context):
        scene = context.scene
        camera = scene.camera

        if not camera:
            self.report({'ERROR'}, "No camera selected.")
            return {'CANCELLED'}

        if camera.name in self.protected_camera_names:
            self.report({'ERROR'}, f"Cannot delete the protected camera: {camera.name}.")
            return {'CANCELLED'}

        try:
            bpy.data.objects.remove(camera, do_unlink=True)
            self.report({'INFO'}, f"Camera '{camera.name}' deleted successfully.")
            self.log_message(f"Camera '{camera.name}' deleted.")

            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    scene.camera = obj
                    self.report({'INFO'}, f"Camera '{obj.name}' set as active.")
                    self.log_message(f"Camera '{obj.name}' set as active.")
                    break
            else:
                scene.camera = None
                self.report({'WARNING'}, "No camera left in the scene.")
                self.log_message("No camera left in the scene.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to delete camera: {str(e)}")
            self.log_message(f"Failed to delete camera: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

    @staticmethod
    def log_message(message):
        """Log messages for debugging purposes."""
        print(f"[Epic Toolbag - RemoveCamera]: {message}")
        
class NavigateHDRI(Operator):
    """Navigate through HDRI thumbnails"""
    bl_idname = "epictoolbag.navigate_hdri"
    bl_label = "Navigate HDRI"

    direction: EnumProperty(
        name="Navigation Direction",
        items=[
            ('NEXT', "Next", "Go to next HDRI"),
            ('PREV', "Previous", "Go to previous HDRI")
        ]
    )

    def execute(self, context):
        pcoll = preview_collections.get("hdri_previews")
        if not pcoll:
            return {'CANCELLED'}

        hdri_list = list(pcoll.keys())
        current_hdri = context.scene.hdri_enum
        
        if current_hdri not in hdri_list:
            # Se o HDRI atual não estiver na lista, seleciona o primeiro
            context.scene.hdri_enum = hdri_list[0]
            return {'FINISHED'}

        current_index = hdri_list.index(current_hdri)

        if self.direction == 'NEXT':
            # Vai para o próximo HDRI, voltando ao início se chegar ao fim
            next_index = (current_index + 1) % len(hdri_list)
            context.scene.hdri_enum = hdri_list[next_index]
        else:
            # Vai para o HDRI anterior, voltando ao fim se chegar ao início
            prev_index = (current_index - 1 + len(hdri_list)) % len(hdri_list)
            context.scene.hdri_enum = hdri_list[prev_index]

        return {'FINISHED'}

classes = [
    AddOrApplyHDRI, 
    RemoveHDRI, 
    CreateLight, 
    RemoveLight, 
    CreateCamera, 
    RemoveCamera, 
    NavigateHDRI,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()