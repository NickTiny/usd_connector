# Blender -> USD Connector

## Introduction
This is an example implementation of how USD support could be improved in Blender. This is an add-on helps track USD data imported from Blender and export only the modifications made, as overrides in a USD layer. 

## Background
#### **The Problem**
Blender's native USD Exporter will always export a full copy of the USD Data out of Blender. 

In most USD based pipelines each DCCs typically will generate layers which contain only the modifications that were added on top of a source file. 

#### **The Solution**
This implementation allows for a Studio to load in some USD data into Blender, such as a model and export only the modifications as a new layer, to be loaded by downstream departments. 

The secondary use case of this implementation is to load "updates" from upstream departments into a Blender session while preserving the local changes in the form of overrides.

## Use Cases

**CG Film Production**
- **3DS Max** is used to create several 3D Models.
- **Blender** is used for environment layout to arrange those models on a set.
- **Maya** is used for animation utilizing the environment as a backdrop.

**Product Design/Advertising**
- **Fusion 360** is used to create a product design.
- **Blender** is used to texture/animate the product.
- **Gaffer** is used to light/render the product.

## Importing USD Data

During Import we take a flattened snapshot of the USD file at the time of import. We also add some metadata to all prims so we can track their sources in later steps. In blender invoking this process is done by using a special importer that takes advantage of USD Hooks in Blender 

<img src="media/import_process.jpg" alt="Import Process"/>


Let's take a look at a real world example comparing the USD data in USD View versus how it is manifested inside of Blender.


On the left we can see our USD data on the right is it's import into Blender and as expected they currently match. (Assuming the data you are importing is supported by Blender's USD importer).

 <img src="media/blender_import_result.jpg" alt="Blender Invoke Import"/>


## Exporting USD Data
At the time of export we temporarily create a full USD Export of our scene using Blender's native USD Exporter, and then we can compare that `tmp_export.usd` to the snapshot of the `source.usd` to find only the changes made in Blender. We then store those changes as overrides in the `export.usd` file.

<img src="media/export_process.jpg" alt="Export Process"/>

 Let's make some simple modifications to our file. Such as changing the position, scale and rotation of our objects. We can then save this data in `export.usd` and see our new composition in the `usdview`.  

 <img src="media/blender_export_result_simple.jpg" alt="Blender Invoke Import" width="800" />


Here is a sample of the USD data that was exported. As you can see, we are only defining overrides on some prims, as opposed to redefining every single prim.

```
#usda 1.0
(
    subLayers = [@source.usda@]
)

over "root"
{
    over "Sphere"
    {
        float3 xformOp:scale = (0.33598453, 0.33598453, 0.33598453)
        double3 xformOp:translate = (0, -0.28551924228668213, 1.9824588298797607)
    }

    over "Cube_A"
    {
        float3 xformOp:rotateXYZ = (-36.15339, 42.571255, -30.909925)
        double3 xformOp:translate = (0, 0, 0)
    }
...

```

## Re-composing scene in usdview
The amazing part of USD is that simply by updating our source file we can re-compose the scene with some modifications. Let's take a look at how that manifests inside of `usdview`.

We can modify our cube to be a pyramid, and we can stretch our sphere out to the shape of a capsule in our `source.usd` file (left) this will automatically be re-composed onto our `export.usd` file (right) while maintaining or transformation modifications. Note the differences in the composition stack on the bottom right panel of each `usdview` window.

 __Although these updates will not be loaded into blender since it stores a copy of our USD data.__

 <img src="media/layer_comp.jpg" alt="Blender Refresh Result" width="800" />


## Re-composing scene in Blender
We can take this a step further, by using Blender's native USD Importer / Exporter with some additional hook logic, we can take the layer stored in `export.usd`, and re-import it back into Blender and remap all the objects effectively "refreshing" our USD data, while maintaining any changes we made.

<img src="media/refresh_process.jpg" alt="Export Process"/>

 Take a look at the same scene from above now re-composed by using this add-ons refresh function.

 Pictured on top is our updated Blender session retaining our modifications. At the bottom we have our `source.usd` file (left) and the results from our `export.usd` usd file (right).

 <img src="media/refresh_result.jpg" alt="Blender Refresh Result" width="800" />

## Authoring New Data
We can also add new data such as new objects in our Blender session and they will be defined in out `export.usd` file as new prims. This also is compatible with our refresh system, as we only remap the objects that are authored by USD Connect. Seamlessly integrating USD data with local blender data.

 <img src="media/new_data_result.jpg" alt="New Data Result" width="800" />

Here is how that manifests in our usd file.
```
#usda 1.0
(
    subLayers = [@source.usda@]
)

over "root"
{
    over "Sphere"
    {
        float3 xformOp:scale = (0.335985, 0.335985, 0.335985)
        double3 xformOp:translate = (0, -0.285519003868103, 1.9824600219726562)
    }

    over "Cube_A"
    {
        float3 xformOp:rotateXYZ = (-36.153408, 42.5713, -30.909904)
        double3 xformOp:translate = (0, 0, 0)
    }


    def Xform "Suzanne"
    {
        custom string userProperties:blender:object_name = "Suzanne"
        float3 xformOp:rotateXYZ = (2.2727437, -27.876757, 6.720067)
        float3 xformOp:scale = (1, 0.99999994, 1)
        double3 xformOp:translate = (2.5021188259124756, 0.6593396663665771, 1.2065078020095825)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]

        def Mesh "Suzanne" (
            active = true
        )
        {
            float3[] extent = [(-1.3671875, -0.8515625, -0.984375), (1.3671875, 0.8515625, 0.984375)]
...
```

## Notes
- Currently this implementation does not support materials
- The override generation logic is still a work in progress
- Consider this project a proof of concept not ready for production use