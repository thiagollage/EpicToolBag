import bpy
import os
import tempfile
import zipfile
import shutil
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator, AddonPreferences
from bpy_extras.io_utils import ImportHelper

def validate_file_extension(file_path):
    """
    Validate file extension and ensure correct file type.
    
    :param file_path: Path to the file
    :return: Tuple (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist."
    
    file_name, file_ext = os.path.splitext(file_path)
    file_ext = file_ext.lower()
    
    # Direct file validations
    valid_direct_extensions = {
        '.blend': 'Blender File',
        '.fbx': 'FBX File',
        '.stl': 'STL File'
    }
    
    # Zip file special handling
    if file_ext == '.zip':
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Check if zip contains only valid file types
                invalid_files = [
                    name for name in zip_ref.namelist() 
                    if os.path.splitext(name)[1].lower() not in {'.blend', '.fbx', '.stl'}
                ]
                
                if invalid_files:
                    return False, f"Invalid files in ZIP: {', '.join(invalid_files)}"
                
                return True, "Valid ZIP file"
        except zipfile.BadZipFile:
            return False, "Invalid ZIP file"
    
    # Direct file validation
    if file_ext in valid_direct_extensions:
        return True, f"Valid {valid_direct_extensions[file_ext]}"
    
    return False, f"Invalid file type. Supported types: {', '.join(valid_direct_extensions.keys())}"

def setup_default_principled_bsdf():
    if "Principled BSDF" not in bpy.data.materials:
        principled_bsdf = bpy.data.materials.new(name="Principled BSDF")
        principled_bsdf.use_nodes = True
        if not principled_bsdf.node_tree.nodes.get('Principled BSDF'):
            principled_node = principled_bsdf.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            principled_node.location = (0, 0)
        bpy.context.preferences.addons['cycles'].preferences.default_material = principled_bsdf

def register_handlers():
    bpy.app.handlers.load_post.append(setup_default_principled_bsdf)

class Preferences(AddonPreferences):
    bl_idname = __package__

    assets_dir: StringProperty(
        name="Assets File",
        subtype='FILE_PATH',
        default="",
        description="Path to the ZIP, CATS, or Blender file containing assets"
    )

    assets_type: EnumProperty(
        name="Asset Type",
        items=[
            ('ZIP', "ZIP Archive", "A ZIP file containing multiple assets"),
            ('BLEND', "Blender File", "A single Blender file with assets"),
            ('FBX', "FBX File", "A single FBX file with assets"),
            ('STL', "STL File", "A single STL file with assets"),

        ],
        default='ZIP',
        description="Type of the asset file"
    )

    info_message: StringProperty(
        name="Information Message",
        default="",
        description="Message to inform the user about the selected file type"
    )

    def draw(self, context):
        layout = self.layout
        if self.info_message:
            layout.label(text=self.info_message, icon='INFO')
        layout.prop(self, "assets_type")
        layout.prop(self, "assets_dir")
        row = layout.row()
        row.operator("epictoolbag.confirm_assets_dir", text="Import Assets", icon='IMPORT')
        row.operator("epictoolbag.clear_assets_dir", text="", icon='TRASH')

    def clear_info_message(self):
        self.info_message = ""

class ClearAssetsDir(Operator):
    bl_idname = "epictoolbag.clear_assets_dir"
    bl_label = "Clear Assets Directory"
    bl_options = {'REGISTER', 'UNDO'}

    clear_type: EnumProperty(
        name="Clear Type",
        items=[
            ('FILE', "Clear File", "Clear the selected file path"),
            ('ALL', "Clear All Assets", "Remove all project assets")
        ],
        default='FILE'
    )

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences
        
        if self.clear_type == 'FILE':
            # File clearing logic
            addon_prefs.assets_dir = ""
            
            if not addon_prefs.assets_dir:
                self.report({'ERROR'}, "No file selected.")
                return {'CANCELLED'}
            
            # Validate the file
            is_valid, message = validate_file_extension(addon_prefs.assets_dir)
            
            if not is_valid:
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
                    
            assets_type = addon_prefs.assets_type
            assets_dir = addon_prefs.assets_dir
            
            if assets_type == 'ZIP':
                addon_prefs.info_message = "ZIP file uploaded successfully."
            elif assets_type == 'BLEND':
                addon_prefs.info_message = "Blend file uploaded successfully."
            elif assets_type == 'FBX':
                addon_prefs.info_message = "FBX file uploaded successfully."
            elif assets_type == 'STL':
                addon_prefs.info_message = "STL file uploaded successfully."
            
            if assets_type == 'ZIP':
                bpy.ops.epictoolbag.import_zip_assets(filepath=assets_dir)
            elif assets_type == 'BLEND':
                bpy.ops.epictoolbag.import_blend_assets(filepath=assets_dir)
            elif assets_type == 'FBX':
                bpy.ops.epictoolbag.import_fbx_assets(filepath=assets_dir)
            elif assets_type == 'STL':
                bpy.ops.epictoolbag.import_stl_assets(filepath=assets_dir)
        
        elif self.clear_type == 'ALL':
            # Clear all project assets logic
            addon_prefs.assets_dir = ""
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()
            
            # Clear unused data
            for material in bpy.data.materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
            for texture in bpy.data.textures:
                if texture.users == 0:
                    bpy.data.textures.remove(texture)
            for mesh in bpy.data.meshes:
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            for image in bpy.data.images:
                if image.users == 0:
                    bpy.data.images.remove(image)
            for collection in bpy.data.collections:
                if collection.asset_data is not None:
                    bpy.data.collections.remove(collection)
            
            self.report({'INFO'}, "All project assets cleared.")
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clear_type")

class ImportZIPAssets(Operator, ImportHelper):
    bl_idname = "epictoolbag.import_zip_assets"
    bl_label = "Import ZIP Assets"
    filename_ext = ".zip;.cats"

    def execute(self, context):
        assets_dir = bpy.path.abspath(self.filepath)
        temp_dir = tempfile.mkdtemp()
        obj_files_not_supported = []
        supported_files_found = False

        try:
            with zipfile.ZipFile(assets_dir, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            self.report({'INFO'}, f"Assets extracted to temporary directory: {temp_dir}")
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith(".blend"):
                        self.import_blend(file_path)
                        supported_files_found = True
                    elif file.endswith(".fbx"):
                        self.import_fbx(file_path)
                        supported_files_found = True
                    elif file.endswith(".stl"):
                        self.import_stl(file_path)
                        supported_files_found = True
                    elif file.endswith(".obj"):
                        obj_files_not_supported.append(file)

            if not supported_files_found:
                self.report({'WARNING'}, "No supported files found in the ZIP archive.")
                context.window_manager.popup_menu(
                    lambda self, context: self.layout.label(text="No supported files found in the ZIP archive."), 
                    title="Warning", 
                    icon='ERROR'
                )

        except Exception as e:
            self.report({'ERROR'}, f"Failed to extract or import assets: {str(e)}")
            return {'CANCELLED'}
        finally:
            shutil.rmtree(temp_dir)

        if obj_files_not_supported:
            warning_message = "OBJ files not supported:\n" + "\n".join(obj_files_not_supported)
            self.report({'WARNING'}, warning_message)
            context.window_manager.popup_menu(lambda self, context: self.layout.label(text=warning_message), title="Warning: OBJ Files Not Supported", icon='ERROR')

        return {'FINISHED'}

    def import_blend(self, filepath):
        try:
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                data_to.objects = [name for name in data_from.objects]

            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
        except Exception as e:
            self.report({'ERROR'}, f"Error importing Blend file: {str(e)}")

    def import_fbx(self, filepath):
        try:
            bpy.ops.import_scene.fbx(filepath=filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Error importing FBX file: {str(e)}")

    def import_stl(self, filepath):
        try:
            bpy.ops.import_mesh.stl(filepath=filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Error importing STL file: {str(e)}")

class ImportBlendAssets(Operator, ImportHelper):
    bl_idname = "epictoolbag.import_blend_assets"
    bl_label = "Import Blender File Assets"
    filename_ext = ".blend"
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        blend_file_path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(blend_file_path):
            self.report({'ERROR'}, "File does not exist: " + blend_file_path)
            return {'CANCELLED'}
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects]
        for obj in data_to.objects:
            if obj is not None:
                bpy.context.collection.objects.link(obj)
        self.report({'INFO'}, "Blender file imported.")
        return {'FINISHED'}
    
class ImportFBXAssets(Operator, ImportHelper):
    bl_idname = "epictoolbag.import_fbx_assets"
    bl_label = "Import FBX Assets"
    filename_ext = ".fbx"
    filter_glob: StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        bpy.ops.import_scene.fbx(filepath=bpy.path.abspath(self.filepath))
        self.report({'INFO'}, "FBX imported.")
        return {'FINISHED'}

class ImportSTLAssets(Operator, ImportHelper):
    bl_idname = "epictoolbag.import_stl_assets"
    bl_label = "Import STL Assets"
    filename_ext = ".stl"
    filter_glob: StringProperty(
        default="*.stl",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        bpy.ops.import_mesh.stl(filepath=bpy.path.abspath(self.filepath))
        self.report({'INFO'}, "STL imported.")
        return {'FINISHED'}
    
class ConfirmAssetsDir(Operator):
    bl_idname = "epictoolbag.confirm_assets_dir"
    bl_label = "Confirm Assets Directory"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences
        
        if not addon_prefs.assets_dir:
            self.report({'ERROR'}, "No file selected.")
            return {'CANCELLED'}
        
        # Validate the file
        is_valid, message = validate_file_extension(addon_prefs.assets_dir)
        
        if not is_valid:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        
        assets_type = addon_prefs.assets_type
        assets_dir = addon_prefs.assets_dir
        
        if assets_type == 'ZIP':
            bpy.ops.epictoolbag.import_zip_assets(filepath=assets_dir)
        elif assets_type == 'BLEND':
            bpy.ops.epictoolbag.import_blend_assets(filepath=assets_dir)
        elif assets_type == 'FBX':
            bpy.ops.epictoolbag.import_fbx_assets(filepath=assets_dir)
        elif assets_type == 'STL':
            bpy.ops.epictoolbag.import_stl_assets(filepath=assets_dir)
        
        self.report({'INFO'}, f"Imported {assets_type} file successfully.")
        return {'FINISHED'}

classes = [
    Preferences,
    ConfirmAssetsDir,
    ClearAssetsDir,
    ImportZIPAssets,
    ImportBlendAssets,
    ImportFBXAssets,
    ImportSTLAssets,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_handlers()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()