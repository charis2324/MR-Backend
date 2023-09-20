import numpy as np
import pyrender
import trimesh


def display_images(images):
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(20, 20))  # specify figure size
    for i, image in enumerate(images):
        ax = fig.add_subplot(
            1, len(images), i + 1
        )  # create a new subplot for each image
        ax.axis("off")  # turn off the axis
        plt.imshow(image)
    plt.show()


def animate_images(images):
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation

    fig = plt.figure()

    im = plt.imshow(images[0], animated=True)

    def updatefig(i):
        im.set_array(images[i])
        return (im,)

    ani = animation.FuncAnimation(
        fig, updatefig, frames=len(images), interval=50, blit=True
    )
    plt.axis("off")
    plt.show()


def mesh_dict_to_trimesh(mesh_dict):
    colors_uint8 = (mesh_dict["colors"] * 255).astype(np.uint8)
    mesh = trimesh.Trimesh(
        vertices=mesh_dict["vertices"],
        faces=mesh_dict["triangles"],
        vertex_colors=colors_uint8,
        process=True,
        validate=True,
    )
    return mesh


def render_preview(mesh_dict, num_frames=180):
    # cleaned_mesh = clean_mesh.clean_mesh(mesh_dict)
    mesh = mesh_dict_to_trimesh(mesh_dict)
    mesh = pyrender.Mesh.from_trimesh(mesh)
    scene = pyrender.Scene(ambient_light=np.array([1, 1, 1, 1.0]))
    scene.add(mesh)
    # pyrender.Viewer(scene, use_raymond_lighting=False)
    camera = pyrender.PerspectiveCamera(yfov=np.radians(45), aspectRatio=1.0)
    r = pyrender.OffscreenRenderer(400, 400)
    images = []
    s = np.sqrt(2) / 2
    default_camera_pose = np.array(
        [
            [0.0, -s, s, 4],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, s, s, 4],
            [0.0, 0.0, 0.0, 1],
        ]
    )
    angles = np.radians(np.linspace(0, 360, num_frames))
    for angle in angles:
        # calculate the rotation matrix
        rotation = np.array(
            [
                [np.cos(angle), -np.sin(angle), 0, 0],
                [np.sin(angle), np.cos(angle), 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        )

        # calculate the camera pose
        camera_pose = np.dot(
            rotation,
            default_camera_pose,
        )

        node = scene.add(camera, pose=camera_pose)
        color, _ = r.render(scene)
        images.append(color)

        # remove the camera for the next rotation
        scene.remove_node(node)

    return images
