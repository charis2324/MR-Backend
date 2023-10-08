import math

import numpy as np
import trimesh


def rotate_mesh(mesh, angle_degrees, direction, center):
    angle_radians = math.radians(angle_degrees)
    rot_matrix = trimesh.transformations.rotation_matrix(
        angle_radians, direction, center
    )

    mesh.apply_transform(rot_matrix)
    return mesh

def rotate_all_geometries(scene, angle_degrees=90, direction=[1, 0, 0], center=[0, 0, 0]):
    """Rotate all geometries in a Scene object."""
    for name, geometry in scene.geometry.items():
        # Apply the rotation to each Trimesh object
        scene.geometry[name] = rotate_mesh(geometry, angle_degrees, direction, center)

def split_model_output(image):
    verts = image.verts.detach().cpu().numpy()
    faces = image.faces.cpu().numpy()
    vertex_colors = np.stack(
        [image.vertex_channels[x].detach().cpu().numpy() for x in "RGB"], axis=1
    )
    return verts, faces, vertex_colors


# From now on we represent meshes in Scene.
def clean_mesh(verts, faces, vertex_colors):
    colors_uint8 = (vertex_colors * 255).astype(np.uint8)
    mesh = trimesh.Trimesh(
        vertices=verts,
        faces=faces,
        vertex_colors=colors_uint8,
        process=True,
        validate=True,
    )
    print(f"Initial mesh: {mesh}")
    if not mesh.is_winding_consistent:
        print("The mesh's winding order is inconsistent, attempting to fix.")
        mesh.fix_winding()

    remove_isolated(mesh)

    if not mesh.is_watertight:
        print("The mesh is not watertight, attempting to fill holes.")
        mesh.fill_holes()

    decimated_mesh = decimate_mesh(mesh)
    print(f"Decimated mesh: {decimated_mesh}")
    map_nearest_color_vertices(decimated_mesh, mesh)
    return trimesh.Scene(decimated_mesh)


def remove_isolated(mesh):
    # Find connected components of the mesh
    cc = trimesh.graph.connected_components(mesh.face_adjacency, min_len=200)
    # Create a mask with the same length as the number of faces in the mesh
    mask = np.zeros(len(mesh.faces), dtype=bool)
    mask[np.concatenate(cc)] = True

    # Update the mesh with the mask
    mesh.update_faces(mask)
    mesh.remove_unreferenced_vertices()


def map_nearest_color_vertices(decimated_mesh, original_mesh):
    tree = original_mesh.kdtree
    _, indices = tree.query(decimated_mesh.vertices)
    decimated_mesh.visual.vertex_colors = original_mesh.visual.vertex_colors[indices]


def decimate_mesh(mesh, ratio=0.1):
    target_face_count = int(len(mesh.faces) * ratio)
    return mesh.simplify_quadric_decimation(target_face_count)


def merge_geometry(scene):
    # Iterate over the geometry items in the scene
    for name, geometry in scene.geometry.items():
        # Try to check if vertex colors are defined
        try:
            if geometry.visual.vertex_colors is not None:
                print("Vertex colors are defined.")
                rgb_vertex_colors = geometry.visual.vertex_colors[:, :3]
                geometry.visual = trimesh.visual.ColorVisuals(
                    mesh=geometry, vertex_colors=rgb_vertex_colors
                )
                continue  # Skip to the next iteration if vertex colors are defined

        # If an AttributeError occurs, print a message and continue to the next block
        except AttributeError:
            print("Vertex colors are not defined.")

        # Try to check if material is defined
        try:
            material = geometry.visual.material
            print("Material is defined.")
            if isinstance(material, trimesh.visual.material.SimpleMaterial):
                material = material.to_pbr()
            if material.baseColorFactor is not None:
                color = material.baseColorFactor
            else:
                color = material.main_color
            vertex_colors = np.tile(color[0:3], (len(geometry.vertices), 1))
            geometry.visual = trimesh.visual.ColorVisuals(
                mesh=geometry, vertex_colors=vertex_colors
            )

        # If an AttributeError occurs, print a message
        except AttributeError:
            print("Material is not defined.")

    # Merge all the geometry items and return the merged geometry
    merged_mesh = trimesh.util.concatenate(scene.geometry.values())
    return merged_mesh
