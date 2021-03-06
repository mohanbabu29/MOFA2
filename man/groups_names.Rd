% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/AllGenerics.R, R/set_methods.R
\name{groups_names}
\alias{groups_names}
\alias{groups_names<-}
\alias{groups_names,MOFA-method}
\alias{groups_names<-,MOFA,character-method}
\title{groups_names: set and retrieve group names}
\usage{
groups_names(object)

groups_names(object) <- value

\S4method{groups_names}{MOFA}(object)

\S4method{groups_names}{MOFA,character}(object) <- value
}
\arguments{
\item{object}{a \code{\link{MOFA}} object.}

\item{value}{character vector with the names for each group}
}
\value{
character vector with the names for each sample group
}
\description{
groups_names: set and retrieve group names
}
\examples{
# Using an existing trained model on simulated data
file <- system.file("extdata", "model.hdf5", package = "MOFA2")
model <- load_model(file)
groups_names(model)
groups_names(model) <- c("my_group")
}
