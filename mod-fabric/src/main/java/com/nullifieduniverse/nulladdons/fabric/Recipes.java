package com.nullifieduniverse.nulladdons.fabric;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.nullifieduniverse.nulladdons.core.Recipe;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Loads the bundled craft recipes ({@code /nulladdons/recipes.json}). */
public final class Recipes {
    private Recipes() {}

    public static List<Recipe> loadBundled() {
        List<Recipe> out = new ArrayList<Recipe>();
        try (InputStream in = Recipes.class.getResourceAsStream("/nulladdons/recipes.json")) {
            if (in == null) return out;
            JsonObject root = JsonParser.parseReader(
                    new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
            JsonArray arr = root.getAsJsonArray("recipes");
            for (JsonElement el : arr) {
                try {
                    JsonObject o = el.getAsJsonObject();
                    String output = o.get("output").getAsString();
                    int outputQty = o.has("outputQty") ? o.get("outputQty").getAsInt() : 1;
                    List<Recipe.Ingredient> inputs = new ArrayList<Recipe.Ingredient>();
                    for (JsonElement ie : o.getAsJsonArray("inputs")) {
                        JsonArray pair = ie.getAsJsonArray();
                        inputs.add(new Recipe.Ingredient(pair.get(0).getAsString(),
                                pair.get(1).getAsInt()));
                    }
                    if (!inputs.isEmpty()) out.add(new Recipe(output, outputQty, inputs));
                } catch (Exception skip) {
                    // Ignore a single malformed entry.
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }
}
