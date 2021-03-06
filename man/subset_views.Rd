% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/subset.R
\name{subset_views}
\alias{subset_views}
\title{Subset views}
\usage{
subset_views(object, views)
}
\arguments{
\item{object}{a \code{\link{MOFA}} object.}

\item{views}{character vector with the views names, numeric vector with the views indices,
or logical vector with the views to be kept as TRUE.}
}
\value{
A \code{\link{MOFA}} object
}
\description{
Method to subset (or sort) views
}
\examples{
# Using an existing trained model on simulated data
file <- system.file("extdata", "model.hdf5", package = "MOFA2")
model <- load_model(file)

# Subset the first view
model <- subset_views(model, views = 1)
}
