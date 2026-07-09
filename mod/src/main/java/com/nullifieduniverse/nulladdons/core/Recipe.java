package com.nullifieduniverse.nulladdons.core;

import java.util.Collections;
import java.util.List;

/** A craft recipe: {@code inputs} (id + count each) combine into {@code output}. */
public final class Recipe {
    public final String output;
    public final int outputQty;
    public final List<Ingredient> inputs;

    public Recipe(String output, int outputQty, List<Ingredient> inputs) {
        this.output = output;
        this.outputQty = Math.max(1, outputQty);
        this.inputs = Collections.unmodifiableList(inputs);
    }

    public static final class Ingredient {
        public final String id;
        public final int count;
        public Ingredient(String id, int count) { this.id = id; this.count = count; }
    }
}
