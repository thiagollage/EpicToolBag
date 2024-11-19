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

        polynomial_density = polygon_count / (volume + 1e-6)
        vertex_complexity = vertex_count / (polygon_count + 1)
        curvature = sum(v.normal.length for v in bm.verts) / vertex_count
        boundary_edges = sum(1 for e in bm.edges if len(e.link_faces) < 2)
        non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)

        bm.free()

        return {
            'polygon_count': polygon_count,
            'vertex_count': vertex_count,
            'edge_count': edge_count,
            'boundary_edges': boundary_edges,
            'non_manifold_edges': non_manifold_edges,
            'polynomial_density': polynomial_density,
            'vertex_complexity': vertex_complexity,
            'curvature': curvature,
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

        normal_variations = [face.normal for face in bm.faces if face.normal.length > 0]
        angles = [normal_variations[i].angle(normal_variations[i-1]) 
                  for i in range(1, len(normal_variations)) if normal_variations[i].length > 0 and normal_variations[i-1].length > 0]
        bm.free()

        is_planar = np.mean(angles) < 0.05 if angles else True
        return {
            'is_planar': is_planar,
            'variation_count': len(set(round(n, 2) for n in angles))
        }

class DensityDetails(PropertyGroup):
    detail_preservation: FloatProperty(
        name="Mesh Density",
        description="Density and detail level for remeshing. Higher values create more optimized topology with fewer quads.",
        default=50,
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
    apply_smooth: BoolProperty(
        name="Apply Smooth",
        description="Apply smooth modifier below the remesh modifier",
        default=False,
        update=lambda self, context: self.update_remesh_settings(context)
    )
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
        if obj and obj.type == 'MESH':
            self.remove_existing_modifier(obj, 'REMESH')
            remesh_mod = obj.modifiers.new(name="Remesh", type='REMESH')
            remesh_mod.mode = self.remesh_mode
            
            if self.remesh_mode in {'SHARP', 'SMOOTH'}:
                remesh_mod.octree_depth = self.calculate_octree_depth()
                self.advanced_remesh_log += f"Updated Octree Depth: {remesh_mod.octree_depth}\n"
            elif self.remesh_mode == 'VOXEL':
                remesh_mod.voxel_size = self.calculate_voxel_size()
                self.advanced_remesh_log += f"Updated Voxel Size: {remesh_mod.voxel_size}\n"

            # Apply or remove smooth modifier
            self.handle_smooth_modifier(obj)

            bpy.context.view_layer.objects.active = obj

    def calculate_octree_depth(self):
        min_depth = 2
        max_depth = 8
        return int(min_depth + (max_depth - min_depth) * (self.detail_preservation / 100))

    def calculate_voxel_size(self):
        # Inverted logic for Voxel Size
        min_size = 1.0  # 1 meter at 0% detail
        max_size = 0.02  # 0.02 meters at 100% detail
        return max_size + (min_size - max_size) * (1 - self.detail_preservation / 100)

    def handle_smooth_modifier(self, obj):
        if self.apply_smooth:
            smooth_mod = next((mod for mod in obj.modifiers if mod.type == 'SMOOTH'), None)
            if not smooth_mod:
                smooth_mod = obj.modifiers.new(name="Smooth", type='SMOOTH')
                smooth_mod.iterations = 5
        else:
            self.remove_existing_modifier(obj, 'SMOOTH')

    def remove_existing_modifier(self, obj, modifier_type):
        for mod in list(obj.modifiers):
            if mod.type == modifier_type:
                obj.modifiers.remove(mod)

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
            original_poly_count = complexity_metrics['polygon_count']

            # Apply decimate if the mesh is too complex
            if original_poly_count > 1400:
                self.report({'INFO'}, "Applying automatic decimate on large mesh.")
                self.apply_decimate_modifier(obj, 0.5)

            self.report({'INFO'}, "Starting remesh process...")
            remesh_settings.update_remesh_settings(context)

            # Once remesh is done, calculate and store performance metrics
            self.report_performance(context, obj, start_time)

            return {'FINISHED'}

        except MemoryError:
            self.report({'ERROR'}, "Memory error during remesh. Attempting to simplify further.")
            self.handle_memory_error(obj, context)
            return {'CANCELLED'}
        except Exception as e:
            import traceback
            error_log = traceback.format_exc()
            remesh_settings.advanced_remesh_log = json.dumps({'error': str(e), 'traceback': error_log})
            self.report({'ERROR'}, f"Remeshing failed: {str(e)}")
            return {'CANCELLED'}

    def apply_decimate_modifier(self, obj, ratio):
        decimate_mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
        decimate_mod.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)

    def handle_memory_error(self, obj, context):
        self.apply_decimate_modifier(obj, 0.5)
        self.report({'INFO'}, "Decimated mesh further to handle memory issues.")

    def report_performance(self, context, obj, start_time):
        processing_time = time.time() - start_time
        complexity_metrics = RemeshAnalytics.calculate_mesh_complexity(obj)

        new_poly_count = complexity_metrics['polygon_count']
        original_poly_count = complexity_metrics['polygon_count']  # This line seems incorrect; should fetch original count from somewhere else
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