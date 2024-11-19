import json
import bpy
import bmesh
import numpy as np
import time
from bpy.types import Operator, PropertyGroup
from bpy.props import FloatProperty, StringProperty, BoolProperty, EnumProperty

class RemeshAnalytics:
    @staticmethod
    def calculate_mesh_complexity(obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        polygon_count = len(bm.faces)
        vertex_count = len(bm.verts)
        edge_count = len(bm.edges)

        volume = sum(abs(face.calc_area() * face.normal.length) for face in bm.faces) / 3

        polygon_density = polygon_count / (volume + 1e-6)
        vertex_complexity = vertex_count / (polygon_count + 1)
        curvatura = sum(v.normal.length for v in bm.verts) / vertex_count
        boundary_edges = sum(1 for e in bm.edges if len(e.link_faces) < 2)
        non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)

        bm.free()

        return {
            'polygon_count': polygon_count,
            'vertex_count': vertex_count,
            'edge_count': edge_count,
            'boundary_edges': boundary_edges,
            'non_manifold_edges': non_manifold_edges,
            'polygon_density': polygon_density,
            'vertex_complexity': vertex_complexity,
            'curvatura': curvatura,
            'volume': volume,
            'is_complex': polygon_count > 1000
        }

class RemeshIntelligentSettings:
    @staticmethod
    def calculate_quad_count(detail_preservation, original_poly_count):
        normalized_detail = detail_preservation / 100.0
        target_count = int(original_poly_count * 0.5)
        quad_count = int(target_count * normalized_detail)
        min_quads = max(10, int(original_poly_count * 0.05))
        return max(min_quads, min(quad_count, target_count))

    @staticmethod
    def detect_planar_surface(obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        normal_variations = [face.normal for face in bm.faces]
        angles = [normal_variations[i].angle(normal_variations[i-1]) for i in range(1, len(normal_variations))]
        bm.free()

        is_planar = np.mean(angles) < 0.05
        return {
            'is_planar': is_planar,
            'variation_count': len(set(round(n, 2) for n in angles))
        }

class DensityDetails(PropertyGroup):
    detail_preservation: FloatProperty(
        name="Mesh Density",
        description="Density and detail level for remeshing. Higher values create more optimized topology with fewer quads.",
        default=100,
        min=0,
        max=100,
        subtype='PERCENTAGE',
        update=lambda self, context: self.update_remesh_settings(context)
    )
    advanced_remesh_log: StringProperty(
        name="Remesh Log",
        description="Detailed log of the remeshing process"
    )
    remesh_performance_metrics: StringProperty(
        name="Remesh Performance Metrics",
        description="JSON string containing performance metrics of the remeshing process"
    )
    preserve_details: BoolProperty(
        name="Preserve Details",
        description="Preserve surface details and edges when remeshing",
        default=True
    )
    symmetry_x: BoolProperty(name="X Symmetry", description="Apply symmetry along X axis", default=False)
    symmetry_y: BoolProperty(name="Y Symmetry", description="Apply symmetry along Y axis", default=False)
    symmetry_z: BoolProperty(name="Z Symmetry", description="Apply symmetry along Z axis", default=False)
    remesh_mode: EnumProperty(
        name="Remesh Mode",
        description="Choose the remeshing mode",
        items=[
            ('SHARP', "Sharp", "Maintain sharp edges"),
            ('SMOOTH', "Smooth", "Smooth the mesh"),
            ('VOXEL', "Voxel", "Use voxel-based remeshing")
        ],
        default='SHARP'
    )

    def update_remesh_settings(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH' and "RemeshApplied" in obj:
            remesh_mode = self.remesh_mode
            remesh_mod = None
            for mod in obj.modifiers:
                if mod.type == 'REMESH':
                    remesh_mod = mod
                    break
            
            if remesh_mod is None:
                remesh_mod = obj.modifiers.new(name="Remesh", type='REMESH')
            
            if remesh_mode in {'SHARP', 'SMOOTH'}:
                octree_depth = self.calculate_octree_depth()
                remesh_mod.octree_depth = octree_depth
                self.advanced_remesh_log += f"Updated Octree Depth: {octree_depth}\n"
            elif remesh_mode == 'VOXEL':
                voxel_size = self.calculate_voxel_size()
                remesh_mod.voxel_size = voxel_size
                self.advanced_remesh_log += f"Updated Voxel Size: {voxel_size}\n"
            
            remesh_mod.mode = remesh_mode
            bpy.context.view_layer.objects.active = obj

    def calculate_octree_depth(self):
        min_depth = 2
        max_depth = 8
        return int(min_depth + (max_depth - min_depth) * (self.detail_preservation / 100))

    def calculate_voxel_size(self):
        min_size = 0.01
        max_size = 0.1
        return min_size + (max_size - min_size) * (1 - self.detail_preservation / 100)

def duplicate_object(obj):
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(new_obj)
    return new_obj

class AdvancedRemesher(Operator):
    bl_idname = "epictoolbag.advanced_remesher"
    bl_label = "Remesh!"
    bl_description = "Performs advanced remeshing operations to optimize mesh topology."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start_time = time.time()
        obj = context.active_object
        remesh_settings = context.scene.epic_advanced_remesh

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No active mesh object found.")
            return {'CANCELLED'}

        if "RemeshApplied" in obj:
            self.report({'WARNING'}, "Remesh has already been applied to this object.")
            return {'CANCELLED'}

        try:
            complexity_metrics = RemeshAnalytics.calculate_mesh_complexity(obj)
            is_planar = RemeshIntelligentSettings.detect_planar_surface(obj)['is_planar']
            original_poly_count = complexity_metrics['polygon_count']
            desired_quad_count = RemeshIntelligentSettings.calculate_quad_count(remesh_settings.detail_preservation, original_poly_count)

            if is_planar or not complexity_metrics['is_complex']:
                return self.perform_remesh(context, start_time, desired_quad_count, remesh_settings.preserve_details, original_poly_count, remesh_settings.remesh_mode)
            else:
                return self.perform_complex_remesh(context, start_time, desired_quad_count, remesh_settings.preserve_details, original_poly_count, remesh_settings.remesh_mode)

        except Exception as e:
            import traceback
            error_log = traceback.format_exc()
            remesh_settings.advanced_remesh_log = json.dumps({'error': str(e), 'traceback': error_log})
            self.report({'ERROR'}, f"Remeshing failed: {str(e)}")
            return {'CANCELLED'}

    def perform_complex_remesh(self, context, start_time, quad_count, preserve_details, original_poly_count, remesh_mode):
        obj = context.active_object
        new_obj = duplicate_object(obj)
        new_obj.name = self.get_unique_name("AutoRemesh")

        self.hide_original_object(obj)

        self.remove_existing_modifier(new_obj, 'REMESH')

        self.apply_decimate_modifier(new_obj, original_poly_count)
        self.apply_remesh_modifier(new_obj, remesh_mode, quad_count, len(new_obj.data.polygons))
        self.apply_smooth_modifier(new_obj, preserve_details)

        new_obj["RemeshApplied"] = True

        # Ensure the new object is selected and active
        self.select_and_activate_object(context, new_obj)

        self.report_performance(context, obj, new_obj, start_time)
        return {'FINISHED'}

    def perform_remesh(self, context, start_time, quad_count, preserve_details, original_poly_count, remesh_mode):
        obj = context.active_object
        new_obj = duplicate_object(obj)
        new_obj.name = self.get_unique_name("AutoRemesh")

        self.hide_original_object(obj)

        self.remove_existing_modifier(new_obj, 'REMESH')

        is_planar = RemeshIntelligentSettings.detect_planar_surface(obj)['is_planar']
        remesh_mode = 'SMOOTH' if is_planar and not preserve_details else remesh_mode

        self.apply_remesh_modifier(new_obj, remesh_mode, quad_count, len(new_obj.data.polygons))
        new_obj["RemeshApplied"] = True

        # Ensure the new object is selected and active
        self.select_and_activate_object(context, new_obj)

        self.report_performance(context, obj, new_obj, start_time)
        return {'FINISHED'}

    def hide_original_object(self, obj):
        obj.hide_set(True)
        obj["RemeshApplied"] = True

    def remove_existing_modifier(self, obj, modifier_type):
        for mod in obj.modifiers:
            if mod.type == modifier_type:
                obj.modifiers.remove(mod)
                self.report({'INFO'}, f"Removed existing {modifier_type} modifier.")

    def apply_decimate_modifier(self, obj, original_poly_count):
        decimate_mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
        decimate_mod.ratio = 0.5 if original_poly_count > 400 else 1.0
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)

    def apply_remesh_modifier(self, obj, mode, quad_count, current_poly_count):
        remesh_mod = obj.modifiers.new(name="Remesh", type='REMESH')
        remesh_mod.mode = mode
        if mode in {'SHARP', 'SMOOTH'}:
            remesh_mod.octree_depth = self.calculate_octree_depth(quad_count, current_poly_count)
        elif mode == 'VOXEL':
            remesh_mod.voxel_size = self.calculate_voxel_size(quad_count, current_poly_count)
        bpy.ops.object.modifier_apply(modifier=remesh_mod.name)

    def apply_smooth_modifier(self, obj, preserve_details):
        smooth_level = 2 if preserve_details else 4
        smooth_mod = obj.modifiers.new(name="Smooth", type='SMOOTH')
        smooth_mod.factor = smooth_level
        smooth_mod.iterations = 5
        bpy.ops.object.modifier_apply(modifier=smooth_mod.name)

    def calculate_octree_depth(self, quad_count, current_poly_count):
        min_depth = 2
        max_depth = 8
        base_depth = quad_count / 500.0

        if current_poly_count > 0:
            adjustment = quad_count / current_poly_count
            base_depth *= adjustment

        return int(max(min_depth, min(max_depth, base_depth)))

    def calculate_voxel_size(self, quad_count, current_poly_count):
        min_size = 0.01
        max_size = 0.1
        normalized_density = quad_count / 100.0
        return min_size + (max_size - min_size) * (1 - normalized_density)

    def report_performance(self, context, original_obj, new_obj, start_time):
        processing_time = time.time() - start_time
        complexity_metrics_original = RemeshAnalytics.calculate_mesh_complexity(original_obj)
        complexity_metrics_new = RemeshAnalytics.calculate_mesh_complexity(new_obj)

        new_poly_count = complexity_metrics_new['polygon_count']
        original_poly_count = complexity_metrics_original['polygon_count']
        reduction_percentage = ((original_poly_count - new_poly_count) / original_poly_count) * 100

        performance_metrics = {
            'complexity_reduction': reduction_percentage,
            'processing_time': processing_time,
            'original_poly_count': original_poly_count,
            'new_poly_count': new_poly_count
        }

        remesh_settings = context.scene.epic_advanced_remesh
        remesh_settings.remesh_performance_metrics = json.dumps(performance_metrics)

        self.report({'INFO'}, 
                    f"Remeshing completed. Reduction: {reduction_percentage:.2f}% "
                    f"Time: {performance_metrics['processing_time']:.4f}s")

    def select_and_activate_object(self, context, obj):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def get_unique_name(self, base_name):
        existing_names = {obj.name for obj in bpy.data.objects}
        if base_name not in existing_names:
            return base_name

        index = 1
        while f"{base_name}.{index:03d}" in existing_names:
            index += 1

        return f"{base_name}.{index:03d}"

def register():
    for cls in [DensityDetails, AdvancedRemesher]:
        bpy.utils.register_class(cls)
    bpy.types.Scene.epic_advanced_remesh = bpy.props.PointerProperty(type=DensityDetails)

def unregister():
    del bpy.types.Scene.epic_advanced_remesh
    for cls in reversed([DensityDetails, AdvancedRemesher]):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()